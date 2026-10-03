"""Value objects for health telemetry invariants."""

from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite


@dataclass(frozen=True)
class TelemetryEventId:
    """Device-generated identity used to safely retry a telemetry event."""

    value: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.value, str)
            or not self.value.strip()
            or len(self.value) > 128
        ):
            raise ValueError("Event ID must contain 1 to 128 non-whitespace characters")


@dataclass(frozen=True)
class HeartRateBpm:
    """A finite heart-rate measurement accepted by the Health context."""

    value: float

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise ValueError("Heart rate must be numeric")
        value = float(self.value)
        if not isfinite(value) or not 0 <= value <= 200:
            raise ValueError("Heart rate must be between 0 and 200 BPM")
        object.__setattr__(self, "value", value)


@dataclass(frozen=True)
class RecordedAt:
    """An offset-aware observation time normalized to UTC."""

    value: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.value, datetime):
            raise TypeError("Observation time must be a datetime")
        if self.value.tzinfo is None or self.value.utcoffset() is None:
            raise ValueError("Observation time must include a timezone")
        object.__setattr__(self, "value", self.value.astimezone(UTC))

    @classmethod
    def now(cls) -> "RecordedAt":
        """Create a value for the current UTC instant."""
        return cls(datetime.now(UTC))

    @classmethod
    def from_optional(cls, value: datetime | None) -> "RecordedAt":
        """Normalize an observation time or use the current instant."""
        return cls.now() if value is None else cls(value)
