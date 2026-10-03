"""Domain entities for the Health bounded context.

The ``HealthRecord`` aggregate and its value objects enforce the invariants for
an accepted telemetry observation. ``SubmittingDevice`` is Health's local
representation of an authenticated submitting device.
"""
from dataclasses import dataclass
from datetime import datetime

from health.domain.value_objects import HeartRateBpm, RecordedAt, TelemetryEventId


@dataclass(frozen=True)
class SubmittingDevice:
    """Health's local representation of a device allowed to submit records."""

    device_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.device_id, str) or not self.device_id.strip():
            raise ValueError("Device identifier cannot be empty")


@dataclass(frozen=True)
class HealthRecord:
    """A valid immutable health observation created through domain behavior.

    A ``HealthRecord`` captures a heart-rate measurement taken by a specific
    smart band device at a given point in time.

    Attributes:
        submitting_device: Health's local concept for the device submitting
            this observation.
        event_id: Device-generated identity used to recognize retries.
        heart_rate: Validated heart-rate measurement.
        recorded_at: Observation time, normalized to UTC.
        timestamp_supplied: Whether the device supplied the observation time.
        id: Persistence identity, or ``None`` before the record is saved.
    """

    submitting_device: SubmittingDevice
    event_id: TelemetryEventId
    heart_rate: HeartRateBpm
    recorded_at: RecordedAt
    timestamp_supplied: bool
    id: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.submitting_device, SubmittingDevice):
            raise TypeError("HealthRecord requires a SubmittingDevice")
        if not isinstance(self.event_id, TelemetryEventId):
            raise TypeError("HealthRecord requires a TelemetryEventId")
        if not isinstance(self.heart_rate, HeartRateBpm):
            raise TypeError("HealthRecord requires a HeartRateBpm value")
        if not isinstance(self.recorded_at, RecordedAt):
            raise TypeError("HealthRecord requires a RecordedAt value")
        if not isinstance(self.timestamp_supplied, bool):
            raise TypeError("HealthRecord timestamp_supplied must be a boolean")
        if self.id is not None:
            if isinstance(self.id, bool) or not isinstance(self.id, int) or self.id <= 0:
                raise ValueError("Persisted health record ID must be a positive integer")

    @classmethod
    def record(
        cls,
        submitting_device: SubmittingDevice,
        event_id: str,
        bpm: float,
        created_at: datetime | None,
    ) -> "HealthRecord":
        """Create a valid health record, enforcing domain invariants."""
        return cls(
            submitting_device,
            TelemetryEventId(event_id),
            HeartRateBpm(bpm),
            RecordedAt.from_optional(created_at),
            created_at is not None,
        )

    @classmethod
    def reconstitute(
        cls,
        submitting_device: SubmittingDevice,
        event_id: str,
        bpm: float,
        created_at: datetime,
        timestamp_supplied: bool,
        record_id: int,
    ) -> "HealthRecord":
        """Rebuild a persisted record while preserving its original input shape."""
        return cls(
            submitting_device,
            TelemetryEventId(event_id),
            HeartRateBpm(bpm),
            RecordedAt(created_at),
            timestamp_supplied,
            record_id,
        )

    @property
    def device_id(self) -> str:
        """Return the submitting device's identifier."""
        return self.submitting_device.device_id

    @property
    def bpm(self) -> float:
        """Return the heart-rate measurement in beats per minute."""
        return self.heart_rate.value

    @property
    def created_at(self) -> datetime:
        """Return the UTC observation time."""
        return self.recorded_at.value

    def with_persistence_id(self, record_id: int) -> "HealthRecord":
        """Return this immutable record with its persistence identity."""
        return HealthRecord(
            self.submitting_device,
            self.event_id,
            self.heart_rate,
            self.recorded_at,
            self.timestamp_supplied,
            record_id,
        )
