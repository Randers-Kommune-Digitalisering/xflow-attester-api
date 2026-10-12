"""
Environment configuration management for the Flask application.
"""
import os

from dotenv import load_dotenv

# loads .env file, will not overide already set enviroment variables (will do nothing when testing, building and deploying)
load_dotenv()


class Config:
    """
    Base configuration class. All other configuration classes should inherit from this.
    """
    SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME")
    POD_NAME = os.getenv("POD_NAME", "pod_name_not_set")
    PORT = int(os.getenv("PORT", "8080"))

    ATTEST_DB_TYPE = os.getenv("ATTEST_DB_TYPE", "postgres").strip()
    ATTEST_DB_HOST = os.getenv("ATTEST_DB_HOST", "").strip()
    ATTEST_DB_NAME = os.getenv("ATTEST_DB_NAME", "").strip()
    ATTEST_DB_USERNAME = os.getenv("ATTEST_DB_USERNAME", "").strip()
    ATTEST_DB_PASSWORD = os.getenv("ATTEST_DB_PASSWORD", "").strip()
    ATTEST_DB_PORT = os.getenv("ATTEST_DB_PORT", "").strip() or None

    SFTP_HOST = os.getenv("SFTP_HOST", "")
    SFTP_USERNAME = os.getenv("SFTP_USERNAME", "")
    SFTP_HOST_KEY = os.getenv("SFTP_HOST_KEY", "")
    SFTP_PASSWORD = os.getenv("SFTP_PASSWORD")
    SFTP_KEY_BASE64 = os.getenv("SFTP_KEY_BASE64", "")
    SFTP_KEY_PASSPHRASE = os.getenv("SFTP_KEY_PASSPHRASE", "")


# DevConfig will be used when FLASK_ENV=dev or is not set
class DevConfig(Config):
    """
    Development configuration.
    """
    DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")


# ProdConfig will be used when FLASK_ENV=prod
class ProdConfig(Config):
    """
    Production configuration.
    """
    DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")


def get_config_class_path() -> str:
    """
    Get the full class path of the configuration class based on the FLASK_ENV environment variable.

    :return: The full class path of the configuration class.
    :raises ValueError: If the FLASK_ENV value is invalid.
    """
    name = _get_config_name()

    if name.lower() == "prod":
        return "utils.config.ProdConfig"
    elif name.lower() == "dev":
        return "utils.config.DevConfig"

    raise ValueError(f"Invalid FLASK_ENV value: {name}. Expected 'dev' or 'prod'.")


def _get_config_name() -> str:
    """
    Get the name of the configuration based on the FLASK_ENV environment variable.

    :return: The name of the configuration.
    """
    return os.getenv("FLASK_ENV", "dev").lower()
