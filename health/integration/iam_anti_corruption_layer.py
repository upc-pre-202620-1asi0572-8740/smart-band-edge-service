"""DDD anti-corruption layer for the Health-to-IAM context relationship."""

from iam.application.services import AuthApplicationService

from health.domain.entities import SubmittingDevice


class IamAntiCorruptionLayer:
    """Translate IAM authentication into Health's submitting-device concept."""

    def __init__(self, iam_authentication_service: AuthApplicationService):
        self._iam_authentication_service = iam_authentication_service

    def authenticated_submitting_device(
        self, device_id: str, credential: str
    ) -> SubmittingDevice | None:
        """Return Health's local device concept when IAM accepts the credentials."""
        if not self._iam_authentication_service.authenticate(device_id, credential):
            return None
        return SubmittingDevice(device_id)
