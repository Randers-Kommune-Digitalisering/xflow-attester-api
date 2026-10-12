"""
Refresh of authorized caseworkers from the user administration CSV on SFTP.
"""
from collections.abc import Mapping

import paramiko
from rkdigi import DatabaseManager
from sqlalchemy.exc import SQLAlchemyError

from attest_database import refresh_authorized_dq_numbers
from utils.sftp import SFTPClient, SFTPError

AUTHORIZATION_CSV_PATH = "/Brugeradministration-da.csv"


def refresh_authorization(
    config: Mapping[str, object],
    database_manager: DatabaseManager,
) -> int:
    """
    Download the authorization CSV and replace the authorized caseworkers.

    :param config: Application configuration holding the SFTP settings.
    :param database_manager: Manager connected to the application database.
    :return: Number of unique authorized DQ numbers.
    :raises SFTPError: If the SFTP authorization server cannot be reached or read.
    :raises ValueError: If the CSV lacks required columns or authorized rows.
    :raises SQLAlchemyError: If replacing the authorized caseworkers fails.
    :raises RuntimeError: If an unexpected error prevents the refresh.
    """
    try:
        authorization_csv = _read_authorization_csv(config)
        return refresh_authorized_dq_numbers(authorization_csv, database_manager)
    except SFTPError:
        raise
    except ValueError:
        raise
    except SQLAlchemyError:
        raise
    except Exception as error:
        raise RuntimeError("Failed to refresh authorized caseworkers.") from error


def _read_authorization_csv(config: Mapping[str, object]) -> str:
    """
    Download the user administration CSV from the SFTP server.

    :param config: Application configuration holding the SFTP settings.
    :return: The decoded CSV content.
    :raises SFTPError: If the SFTP authorization server cannot be reached or read.
    """
    sftp_client = SFTPClient(
        host=config["SFTP_HOST"],
        username=config["SFTP_USERNAME"],
        host_key=config["SFTP_HOST_KEY"],
        password=config["SFTP_PASSWORD"],
    )
    sftp_connection = sftp_client.get_connection()
    if sftp_connection is None:
        raise SFTPError("Unable to connect to the SFTP authorization server.")

    try:
        with sftp_connection.open(AUTHORIZATION_CSV_PATH, "rb") as csv_file:
            csv_bytes = csv_file.read()
    except (OSError, paramiko.SSHException) as error:
        raise SFTPError("Unable to read the authorization CSV from the SFTP server.") from error
    finally:
        sftp_connection.close()

    return csv_bytes.decode("utf-16")
