"""
API endpoints for the Flask application.
"""
import logging

from flask import Blueprint, Response, current_app, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from attest_database import (is_authorized_sagsbehandler,
                             save_attestation_request)
from attest_validation import (REQUIRED_ATTEST_REQUEST_FIELDS,
                               VALID_ATTEST_TYPES, extract_sagsbehandler_dq,
                               parse_attest_types, validate_attest_request,
                               validate_attest_types, validate_json_structure)
from authorization import refresh_authorization as refresh_authorized_sagsbehandlere
from utils.logging import count_error
from utils.sftp import SFTPError

api = Blueprint("api", __name__, url_prefix="/api")
logger = logging.getLogger(__name__)


@api.route("/receive_data", methods=["POST"])
def receive_data() -> tuple[Response, int]:
    """
    Validate, authorize, and persist an incoming X-Flow request.

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

    database_manager = current_app.extensions.get("database_manager")
    if database_manager is None:
        return jsonify({"error": "Database is not configured."}), 503

    sagsbehandler_dq = extract_sagsbehandler_dq(payload["sagsbehandler"])
    is_approved = is_authorized_sagsbehandler(
        sagsbehandler_dq or "",
        database_manager,
    )
    approval_status = "approved" if is_approved else "denied"
    # Save every valid request, including those with denied approval.
    try:
        request_id = save_attestation_request(
            payload,
            attest_types,
            is_approved,
            database_manager,
        )
    except Exception as error:
        count_error(error)
        logger.error("Failed to save attestation request: %s", error)
        return jsonify({"error": "Unable to save attestation request."}), 500

    return jsonify({
        "status": "data received",
        "approvalStatus": approval_status,
        "requestId": request_id,
    }), 200


@api.route("/refresh_authorization", methods=["POST"])
def refresh_authorization() -> tuple[Response, int]:
    """
    Endpoint to refresh the authorization status of the sagsbehandler.

    :return: JSON result and HTTP 200, or an error and HTTP 500/502/503
    """
    database_manager = current_app.extensions.get("database_manager")
    if database_manager is None:
        return jsonify({"error": "Database is not configured."}), 503

    try:
        authorized_count = refresh_authorized_sagsbehandlere(
            current_app.config,
            database_manager,
        )

    except SFTPError as error:
        count_error(error)
        logger.error("Authorization refresh failed: %s", error)
        return jsonify({"error": "Unable to fetch authorization data."}), 502

    except ValueError as error:
        count_error(error)
        logger.error("Authorization refresh failed: invalid authorization data.")
        return jsonify({"error": "Invalid authorization data."}), 502

    except SQLAlchemyError as error:
        count_error(error)
        logger.error("Authorization refresh failed: database unavailable.")
        return jsonify({"error": "Unable to update authorization data."}), 503

    except RuntimeError as error:
        count_error(error)
        logger.error("Authorization refresh failed: unexpected error.")
        return jsonify({"error": "Unable to refresh authorization data."}), 500

    return jsonify({
        "status": "authorization refreshed",
        "authorizedCount": authorized_count,
    }), 200
