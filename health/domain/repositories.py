"""Repository abstraction for Health domain aggregates."""

from dataclasses import dataclass
from typing import Protocol

from health.domain.entities import HealthRecord


@dataclass(frozen=True)
class HealthRecordSaveResult:
    """Persisted record and whether this call created the telemetry event."""

    record: HealthRecord
    created: bool


class HealthRecordRepository(Protocol):
    """Persistence contract for Health records."""

    def save_idempotently(self, health_record: HealthRecord) -> HealthRecordSaveResult:
        """Persist a record or return its matching prior submission."""
        ...
