"""
SQLAlchemy engine factory for the supported database types.
"""
import sqlalchemy

DRIVERS = {
    "mssql": "mssql+pymssql",
    "mariadb": "mariadb+pymysql",
    "postgresql": "postgresql+psycopg2",
}


class DatabaseClient:
    """
    Create a SQLAlchemy engine for an MSSQL, MariaDB or PostgreSQL database.

    :param db_type: One of ``mssql``, ``mariadb`` or ``postgresql``.
    :param database: Database name.
    :param username: Database user.
    :param password: Database password.
    :param host: Database host.
    :param port: Optional database port.
    :raises ValueError: If the database type is not supported.
    """

    def __init__(
        self: "DatabaseClient",
        db_type: str,
        database: str,
        username: str,
        password: str,
        host: str,
        port: str | None = None,
    ) -> None:
        driver = DRIVERS.get(db_type.lower())
        if driver is None:
            raise ValueError(f"Invalid database type {db_type}")

        if port:
            host = f"{host}:{port}"

        self.engine = sqlalchemy.create_engine(f"{driver}://{username}:{password}@{host}/{database}")
