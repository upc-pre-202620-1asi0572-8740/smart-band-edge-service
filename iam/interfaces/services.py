"""HTTP interface for the IAM bounded context.

Exposes IAM HTTP routes and adapts request data for IAM application use cases.
"""
from flask import Blueprint, current_app, jsonify, request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

iam_api = Blueprint("iam_api", __name__)


class AuthRequest(BaseModel):
    """Request contract for authenticating one registered device."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    device_id: str = Field(..., min_length=1, description="Identifier of the device.")


@iam_api.route("/api/v1/iam/authentications", methods=["POST"])
def authenticate_device():
    """Authenticate a device using its identity and API key.

    The device identity is supplied in the JSON body and its API key in the
    ``X-API-Key`` header. This endpoint reports authentication outcome only;
    device provisioning and lifecycle management are not exposed over HTTP.

    Responses:
        ``200`` when the registered device is active and the credential
        matches; ``400`` for invalid JSON or a malformed payload; ``401`` for
        missing or rejected credentials; ``415`` for a non-JSON request.

    The IAM application use case is obtained from the Flask application
    composition, so HTTP requests use the same service instance as other
    adapters.
    """
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    request_data = request.get_json(silent=True)
    if request_data is None:
        return jsonify({"error": "Invalid JSON request body"}), 400

    try:
        auth_request = AuthRequest.model_validate(request_data)
    except ValidationError:
        return jsonify({"error": "Invalid authentication request"}), 400

    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return jsonify({"error": "Missing X-API-Key"}), 401

    if not current_app.extensions["iam_authentication_service"].authenticate(
        auth_request.device_id, api_key
    ):
        return jsonify({"error": "Invalid device_id or API key"}), 401

    return jsonify({"device_id": auth_request.device_id, "authenticated": True}), 200
