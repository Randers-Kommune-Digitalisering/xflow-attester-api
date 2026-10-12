"""
Main entry point for the Flask application.
"""
from flask import Flask, Response, jsonify, request
from prometheus_client import generate_latest

from attest_database import refresh_authorized_dq_numbers
from utils.config import get_config_class_path
from utils.database import DatabaseClient
from utils.logging import error_counter, set_logging_configuration
from utils.sftp import SFTPClient

AUTHORIZATION_CSV_PATH = "/Brugeradministration-da.csv"


def create_app(config_object: str = "utils.config.DevConfig") -> Flask:
    """
    Create and configure the Flask application.

    :param config_object: The configuration object to use.
    :return: The Flask application instance.
    """
    app = Flask(__name__)
    app.config.from_object(config_object)

    debug = bool(app.config.get("DEBUG", False))
    set_logging_configuration(debug=debug)

    authorization_csv = _read_authorization_csv(app)

    database_client = DatabaseClient(
        db_type=app.config["ATTEST_DB_TYPE"],
        database=app.config["ATTEST_DB_NAME"],
        username=app.config["ATTEST_DB_USERNAME"],
        password=app.config["ATTEST_DB_PASSWORD"],
        host=app.config["ATTEST_DB_HOST"],
        port=app.config["ATTEST_DB_PORT"],
    )
    database_engine = database_client.engine
    app.extensions["database_engine"] = database_engine
    refresh_authorized_dq_numbers(authorization_csv, database_engine)

    from api_endpoints import api
    app.register_blueprint(api)
    app.add_url_rule("/metrics", "metrics", view_func=generate_latest)

    @app.after_request
    def count_server_errors(response: Response) -> Response:
        """
        Count server-side (5xx) HTTP responses using Prometheus metrics.

        :param response: The outgoing Flask response object.
        :return: The unmodified response.
        """
        if 500 <= response.status_code <= 599:
            error_counter.labels(
                endpoint=request.path,
                status=str(response.status_code),
            ).inc()

        return response

    @app.get("/healthz")
    def healthz() -> tuple[dict, int]:
        """
        Health check endpoint.

        :return: A JSON response indicating the health status.
        """
        return jsonify({"status": "ok"}), 200

    return app


def _read_authorization_csv(app: Flask) -> str:
    """
    Download the user administration CSV from the SFTP server.

    :param app: The Flask application holding the SFTP configuration.
    :return: The decoded CSV content.
    :raises RuntimeError: If the SFTP authorization server cannot be reached.
    """
    sftp_client = SFTPClient(
        host=app.config["SFTP_HOST"],
        username=app.config["SFTP_USERNAME"],
        password=app.config["SFTP_PASSWORD"],
        key_base64=app.config["SFTP_KEY_BASE64"],
        key_pass=app.config["SFTP_KEY_PASS"],
    )
    sftp_connection = sftp_client.get_connection()
    if sftp_connection is None:
        raise RuntimeError("Unable to connect to the SFTP authorization server.")

    try:
        with sftp_connection.open(AUTHORIZATION_CSV_PATH, "rb") as csv_file:
            return csv_file.read().decode("utf-16")
    finally:
        sftp_connection.close()


# WSGI entrypoint for `gunicorn --chdir src main:app`
app = create_app(config_object=get_config_class_path())


if __name__ == "__main__":  # pragma: no cover
    app.run(debug=app.config["DEBUG"], host="0.0.0.0", port=int(app.config.get("PORT")))
