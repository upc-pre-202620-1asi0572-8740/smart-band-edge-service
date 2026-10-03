"""Repository implementation for the Health bounded context.

Provides the persistence adapter that maps between the
:class:`~health.domain.entities.HealthRecord` domain entity and the
:class:`~health.infrastructure.models.HealthRecord` Peewee ORM model.

Following the Repository pattern, callers in the application layer interact
only with domain entities and are shielded from ORM/database details.
"""
from datetime import UTC, datetime

import peewee

from health.domain.errors import TelemetryEventConflict
from health.domain.entities import HealthRecord, SubmittingDevice
from health.domain.repositories import HealthRecordSaveResult
from health.infrastructure.models import HealthRecord as HealthRecordModel


class HealthRecordRepository:
    """Repository that persists and reconstructs :class:`~health.domain.entities.HealthRecord` entities.

    Acts as an in-process collection of domain entities backed by the SQLite
    database.  The mapping between the ORM model and the domain entity is
    handled entirely within this class, keeping the domain layer free of
    infrastructure concerns.
    """

    def migrate_schema(self) -> None:
        """Add the event identifier and unique device/event constraint."""
        database = HealthRecordModel._meta.database
        with database.atomic("IMMEDIATE"):
            columns = {
                column.name for column in database.get_columns("health_records")
            }
            if "event_id" not in columns:
                database.execute_sql(
                    'ALTER TABLE "health_records" ADD COLUMN "event_id" '
                    "VARCHAR(128) NULL"
                )
            if "timestamp_supplied" not in columns:
                database.execute_sql(
                    'ALTER TABLE "health_records" ADD COLUMN "timestamp_supplied" '
                    "BOOLEAN NOT NULL DEFAULT 1"
                )
            database.execute_sql(
                'CREATE UNIQUE INDEX IF NOT EXISTS '
                '"health_records_device_event_id_unique" '
                'ON "health_records" ("device_id", "event_id")'
            )

    def save_idempotently(
        self, health_record: HealthRecord
    ) -> HealthRecordSaveResult:
        """Persist a record or return the matching earlier device event.

        The database uniqueness constraint protects concurrent retries; payload
        comparison ensures an event ID cannot be reused for different data.
        """
        database = HealthRecordModel._meta.database
        try:
            with database.atomic("IMMEDIATE"):
                existing = self._find_event(
                    health_record.device_id, health_record.event_id.value
                )
                if existing is not None:
                    return HealthRecordSaveResult(
                        self._matching_event(existing, health_record), False
                    )
                row = HealthRecordModel.create(
                    device_id=health_record.device_id,
                    event_id=health_record.event_id.value,
                    bpm=health_record.bpm,
                    created_at=health_record.created_at,
                    timestamp_supplied=health_record.timestamp_supplied,
                )
                return HealthRecordSaveResult(self._to_entity(row), True)
        except peewee.IntegrityError:
            existing = self._find_event(
                health_record.device_id, health_record.event_id.value
            )
            if existing is None:
                raise
            return HealthRecordSaveResult(
                self._matching_event(existing, health_record), False
            )

    @staticmethod
    def _find_event(device_id: str, event_id: str):
        return HealthRecordModel.get_or_none(
            (HealthRecordModel.device_id == device_id)
            & (HealthRecordModel.event_id == event_id)
        )

    def _matching_event(
        self, existing: HealthRecordModel, submitted: HealthRecord
    ) -> HealthRecord:
        persisted = self._to_entity(existing)
        if (
            persisted.bpm != submitted.bpm
            or persisted.timestamp_supplied != submitted.timestamp_supplied
            or (
                submitted.timestamp_supplied
                and persisted.created_at != submitted.created_at
            )
        ):
            raise TelemetryEventConflict
        return persisted

    @staticmethod
    def _to_entity(row: HealthRecordModel) -> HealthRecord:
        created_at = row.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return HealthRecord.reconstitute(
            SubmittingDevice(row.device_id),
            row.event_id,
            row.bpm,
            created_at,
            row.timestamp_supplied,
            row.id,
        )
