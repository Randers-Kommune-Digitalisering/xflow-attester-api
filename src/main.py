"""
Main entry point for the Flask application.
"""
from flask import Flask, Response, got_request_exception, jsonify, request
from prometheus_client import generate_latest
from rkdigi import DatabaseManager

from authorization import refresh_authorization
from model import Base
from utils.config import get_config_class_path
from utils.logging import (count_error, http_error_counter, set_logging_configuration)


def create_app(config_object: str = "utils.config.DevConfig") -> Flask:
    """
    Create and configure the Flask application.

    :param config_object: The configuration object to use.
    :return: The Flask application instance.
    :raises Exception: Re-raises any startup error after counting it.
    """
    app = Flask(__name__)
    app.config.from_object(config_object)

    debug = bool(app.config.get("DEBUG", False))
    set_logging_configuration(debug=debug)

    try:
        db_port = app.config["ATTEST_DB_PORT"]
        # Creates missing tables from the models after verifying the connection.
        database_manager = DatabaseManager(
            profile_name="attest_db",
            db_type=app.config["ATTEST_DB_TYPE"],
            database=app.config["ATTEST_DB_NAME"],
            username=app.config["ATTEST_DB_USERNAME"],
            password=app.config["ATTEST_DB_PASSWORD"],
            host=app.config["ATTEST_DB_HOST"],
            port=int(db_port) if db_port else None,
            base_model=Base,
        )
        app.extensions["database_manager"] = database_manager
        refresh_authorization(app.config, database_manager)
    except Exception as error:
        count_error(error)
        raise

    # Fires for unhandled exceptions raised while handling a request.
    got_request_exception.connect(_on_request_exception, app)

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
            http_error_counter.labels(
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


def _on_request_exception(sender: Flask, exception: Exception, **extra: object) -> None:
    """
    Count unhandled exceptions raised during request handling.

    :param sender: The Flask application that sent the signal.
    :param exception: The unhandled exception.
    :param **extra: Additional signal arguments (unused).
    """
    count_error(exception)


# WSGI entrypoint for `gunicorn --chdir src main:app`
app = create_app(config_object=get_config_class_path())


if __name__ == "__main__":  # pragma: no cover
    app.run(debug=app.config["DEBUG"], host="0.0.0.0", port=int(app.config.get("PORT")))
