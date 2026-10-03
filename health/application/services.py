"""Application services for the Health bounded-context.

Application services coordinate Health use cases: they invoke domain
behavior, coordinate with other bounded contexts through integration
components, and persist outcomes through repositories.
"""

from datetime import datetime

from health.application.errors import DeviceAuthenticationFailed
from health.domain.entities import HealthRecord, SubmittingDevice
from health.domain.repositories import HealthRecordRepository, HealthRecordSaveResult
from health.infrastructure.repositories import HealthRecordRepository as HealthRecordRepositoryImpl
from health.integration.iam_anti_corruption_layer import IamAntiCorruptionLayer


class HealthRecordApplicationService:
    """Coordinate the use case for accepting a health telemetry event.

    The service asks the Health-to-IAM anti-corruption layer to authenticate
    the submitting device, creates a valid
    :class:`~health.domain.entities.HealthRecord` through aggregate behavior,
    and delegates idempotent persistence to the Health repository.
    """

    def __init__(
        self,
        iam_anti_corruption_layer: IamAntiCorruptionLayer,
        health_record_repository: HealthRecordRepository | None = None,
    ):
        """Initialize the service with its context integration and repository."""
        self.health_record_repository = health_record_repository or HealthRecordRepositoryImpl()
        self.iam_anti_corruption_layer = iam_anti_corruption_layer

    def create_health_record(
        self,
        device_id: str,
        event_id: str,
        bpm: float,
        created_at: datetime | None,
        api_key: str,
    ) -> HealthRecordSaveResult:
        """Accept and persist one device-submitted telemetry event.

        Authentication is delegated to the IAM anti-corruption layer. Health
        then creates the record through its aggregate and persists it
        idempotently, distinguishing a new event from an identical retry.

        Args:
            device_id: Identity of the device submitting the reading.
            event_id: Stable device-generated identity reused for retries.
            bpm: Heart-rate measurement in beats per minute.
            created_at: Parsed observation time, or ``None`` to use the
                current UTC time.
            api_key: Credential presented for device authentication.

        Returns:
            The persisted record and whether it was newly created or an
            identical retry.

        Raises:
            DeviceAuthenticationFailed: The IAM context rejects the device's
                credentials.
            ValueError: The Health domain rejects a value or invariant.
            :class:`~health.domain.errors.TelemetryEventConflict`: The device
                reused an event ID for different telemetry.
        """
        submitting_device = self.iam_anti_corruption_layer.authenticated_submitting_device(
            device_id, api_key
        )
        if submitting_device is None:
            raise DeviceAuthenticationFailed
        record = HealthRecord.record(
            SubmittingDevice(submitting_device.device_id), event_id, bpm, created_at
        )
        return self.health_record_repository.save_idempotently(record)
