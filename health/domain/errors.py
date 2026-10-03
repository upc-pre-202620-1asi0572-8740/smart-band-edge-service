"""Domain errors for Health telemetry ingestion."""


class TelemetryEventConflict(Exception):
    """Raised when one device reuses an event ID for different telemetry."""
