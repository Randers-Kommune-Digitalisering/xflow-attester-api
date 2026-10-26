"""
Centralized Werkzeug logging configuration.
"""
import logging
import re
import sys
from wsgiref.simple_server import WSGIRequestHandler

from prometheus_client import Counter  # , Gauge, Summary
from sqlalchemy.exc import SQLAlchemyError

from utils.sftp import SFTPError

# Prometheus metrics
http_error_counter = Counter(
    name="http_server_errors",
    documentation="Number of 5xx responses",
    labelnames=["endpoint", "status"],
)
error_counter = Counter(
    name="error_count",
    documentation="Number of errors encountered",
    labelnames=["error_type"],
)


def count_error(error: BaseException) -> None:
    """
    Increment the error counter with a label based on the exception type.

    :param error: The exception that was raised.
    """
    if isinstance(error, SQLAlchemyError):
        error_type = "db"
    elif isinstance(error, SFTPError):
        error_type = "sftp"
    else:
        error_type = "python"

    error_counter.labels(error_type=error_type).inc()


def set_logging_configuration(debug: bool = False) -> None:
    """
    Set the logging configuration for the application.

    :param debug: If True, set the logging level to DEBUG. Otherwise, set it to INFO.
    """
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        stream=sys.stdout,
        level=log_level,
        format="[%(asctime)s] %(levelname)s - %(name)s - %(module)s:%(funcName)s - %(message)s",
        datefmt="%d-%m-%Y %H:%M:%S",
    )

    # Best-effort: only affects the Werkzeug dev server.
    try:
        from werkzeug import serving

        disable_endpoint_logs(serving, ("/healthz", "/metrics"))
    except Exception:
        pass


def disable_endpoint_logs(serving_module: type, disabled_endpoints: tuple[str, ...]) -> None:
    """
    Disable logging for specific endpoints in the Werkzeug dev server.

    :param serving_module: The Werkzeug serving module.
    :param disabled_endpoints: A tuple of endpoint paths to disable logging for.
    """
    parent_log_request = serving_module.WSGIRequestHandler.log_request

    def log_request(self: WSGIRequestHandler, *args: tuple, **kwargs: dict) -> None:
        if not any(re.match(f"{de}$", self.path) for de in disabled_endpoints):
            parent_log_request(self, *args, **kwargs)

    serving_module.WSGIRequestHandler.log_request = log_request
