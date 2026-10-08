import logging
from flask import Flask
from healthcheck import HealthCheck
from prometheus_client import generate_latest

from utils.logging import set_logging_configuration, is_ready_gauge, last_updated_gauge
from utils.config import DEBUG, PORT, POD_NAME
# from api_endpoints import api_endpoints  # Uncomment to import enpoints


set_logging_configuration()
logger = logging.getLogger(__name__)


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

    return app


app = create_app()


if __name__ == '__main__':  # pragma: no cover
    logger.info("Starting Flask application")
    from sqlalchemy import create_engine, inspect
    from utils.config import DB_CONNECTION_STRING

    logger.info(f"DB Connection String: {DB_CONNECTION_STRING}")

    engine = create_engine(DB_CONNECTION_STRING)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print("Tables in the database:")
    for table in tables:
        print(table)

    app.run(debug=DEBUG, host='0.0.0.0', port=PORT)
