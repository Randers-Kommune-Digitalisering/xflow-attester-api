import logging
import os
import threading
import time

from flask import Flask
from healthcheck import HealthCheck
from prometheus_client import generate_latest

from utils.logging import set_logging_configuration, is_ready_gauge, last_updated_gauge
from utils.config import DEBUG, PORT, POD_NAME
from browserautomation import test_selenium, test_playwright_browserless
# from api_endpoints import api_endpoints  # Uncomment to import enpoints


set_logging_configuration()


_startup_jobs_lock = threading.Lock()
_startup_jobs_started = False


def _run_browser_automation_once():
    try:
        test_selenium()
    except Exception:
        logging.exception("Selenium startup job failed")

    try:
        test_playwright_browserless()
    except Exception:
        logging.exception("Playwright startup job failed")


def _browser_automation_scheduler(interval_seconds=120):
    _run_browser_automation_once()

    while True:
        time.sleep(interval_seconds)
        _run_browser_automation_once()


def _should_start_background_jobs():
    # In debug mode, avoid double-starting due to Werkzeug reloader parent process.
    return (not DEBUG) or (os.environ.get('WERKZEUG_RUN_MAIN') == 'true')


def _start_background_jobs_once():
    global _startup_jobs_started

    if not _should_start_background_jobs():
        return

    with _startup_jobs_lock:
        if _startup_jobs_started:
            return

        thread = threading.Thread(
            target=_browser_automation_scheduler,
            name='browser-automation-scheduler',
            daemon=True,
        )
        thread.start()
        _startup_jobs_started = True


def create_app():
    app = Flask(__name__)
    health = HealthCheck()
    app.add_url_rule('/healthz', 'healthcheck', view_func=lambda: health.run())
    app.add_url_rule('/metrics', 'metrics', view_func=generate_latest)

    # app.register_blueprint(api_endpoints)  # Uncomment to add enpoints from api_endpoints.py

    @app.before_request
    def set_ready():
        is_ready_gauge.labels(job_name=POD_NAME, error_type=None).set(1)
        last_updated_gauge.set_to_current_time()

    _start_background_jobs_once()

    return app


app = create_app()


if __name__ == '__main__':  # pragma: no cover
    app.run(debug=DEBUG, host='0.0.0.0', port=PORT)
