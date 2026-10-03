"""Application errors raised by Health use cases."""


class DeviceAuthenticationFailed(Exception):
    """Raised when a device is not authorized to submit a health record."""
