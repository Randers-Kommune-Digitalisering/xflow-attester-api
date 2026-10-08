import logging

from flask import Blueprint, Response, current_app, jsonify, request

from attest_database import (is_authorized_sagsbehandler,
                             save_attestation_request)
from attest_validation import (REQUIRED_ATTEST_REQUEST_FIELDS,
                               VALID_ATTEST_TYPES, extract_sagsbehandler_dq,
                               parse_attest_types, validate_attest_request,
                               validate_attest_types, validate_json_structure)

logger = logging.getLogger(__name__)
api_endpoints = Blueprint('api', __name__, url_prefix='/api')

# NB: uncomment code in main.py to enable these endpoints
# Any endpoints added here will be available at /api/<endpoint>
# - e.g. http://127.0.0.1:8080/api/example


@api_endpoints.route("/receive_data", methods=["POST"])
def receive_data() -> tuple[Response, int]:
    """Validate, authorize, and persist an incoming X-Flow request.

    Structurally valid requests are saved even when the requester is not
    authorized; those requests are marked for manual handling.

    :return: JSON result and HTTP 200, or validation errors and HTTP 400
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    errors = validate_json_structure(payload, REQUIRED_ATTEST_REQUEST_FIELDS)
    if errors:
        return jsonify({"errors": errors}), 400

    # Normalize a single type or comma-separated selection before validation.
    attest_types, errors = parse_attest_types(payload["attestType"])
    if errors:
        return jsonify({"errors": errors}), 400

    errors = validate_attest_types(attest_types, VALID_ATTEST_TYPES)
    if errors:
        return jsonify({"errors": errors}), 400

    errors = validate_attest_request(payload, attest_types)
    if errors:
        return jsonify({"errors": errors}), 400

    database_engine = current_app.extensions.get("database_engine")
    if database_engine is None:
        return jsonify({"error": "Database is not configured."}), 503

    sagsbehandler_dq = extract_sagsbehandler_dq(payload["sagsbehandler"])
    is_approved = is_authorized_sagsbehandler(
        sagsbehandler_dq or "",
        database_engine,
    )
    approval_status = "approved" if is_approved else "denied"
    # Save every valid request, including those with denied approval.
    request_id = save_attestation_request(
        payload,
        attest_types,
        is_approved,
        database_engine,
    )
    return jsonify({
        "status": "data received",
        "approvalStatus": approval_status,
        "requestId": request_id,
    }), 200
