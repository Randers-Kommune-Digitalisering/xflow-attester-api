"""Database access for authorized caseworkers and submitted forms."""

import csv
import datetime
import re
import uuid
from io import StringIO

from sqlalchemy import (Boolean, Column, DateTime, Engine, Integer, MetaData,
                        String, Table, insert, text)

from attest_validation import (DQ_NUMBER_PATTERN, extract_sagsbehandler_dq,
                               extract_sagsbehandler_name)

CSV_DQ_COLUMN = "Lokalt brugernavn"
CSV_ROLE_COLUMN = "Rolle"
AUTHORIZED_ROLES = {"leder", "stedfortraeder for leder"}

metadata = MetaData()
attestation_requests = Table(
    "attestation_requests",
    metadata,
    Column("requestId", String(36), primary_key=True),
    Column("attestType", Integer, primary_key=True),
    Column("rekvirentDQ", String, nullable=False),
    Column("rekvirentNavn", String, nullable=False),
    Column("rekvisitusCPR", String, nullable=False),
    Column("attestSubType", Integer),
    Column("erGodkendt", Boolean, nullable=False),
    Column("erBestilt", Boolean, nullable=False),
    Column("erModtaget", Boolean, nullable=False),
    Column("erJournaliseret", Boolean, nullable=False),
    Column("erSendtTilManuelBehandling", Boolean, nullable=False),
    Column("erAdviseret", Boolean, nullable=False),
    Column("sbsysSagsNr", String),
    Column("sbsysSagsID", Integer),
    Column("anmodetTS", DateTime(timezone=True), nullable=False),
    Column("bestiltTS", DateTime(timezone=True)),
    Column("modtagetTS", DateTime(timezone=True)),
    Column("journaliseretTS", DateTime(timezone=True)),
    Column("adviseretTS", DateTime(timezone=True)),
)


def refresh_authorized_dq_numbers(
    csv_content: str,
    database_engine: Engine,
) -> int:
    """Replace authorized DQ numbers with entries from the CSV.

    :param csv_content: administration CSV content as a string
    :param database_engine: Engine connected to the application database
    :return: Number of unique authorized DQ numbers
    """
    # Validate the file before opening the transaction
    # Bad input cannot clear the list.
    dq_numbers = parse_authorized_dq_numbers(csv_content)
    initialize_database(database_engine)

    # Keep the full replacement atomic
    # A failed insert rolls back the deletion.
    with database_engine.begin() as connection:
        connection.execute(text("DELETE FROM authorized_sagsbehandlere"))
        connection.execute(
            text("INSERT INTO authorized_sagsbehandlere"
                 " (dq_number) VALUES (:dq_number)"),
            [{"dq_number": dq_number} for dq_number in sorted(dq_numbers)],
        )

    return len(dq_numbers)


def is_authorized_sagsbehandler(
        dq_number: str, database_engine: Engine) -> bool:
    """Check whether a DQ number belongs to a leader or deputy leader.

    :param dq_number: DQ number extracted from the form
    :param database_engine: Engine connected to the application database
    :return: True if the DQ number is authorized
    """
    normalized_dq = dq_number.strip().upper()
    with database_engine.connect() as connection:
        result = connection.execute(
            text(
                "SELECT 1 FROM authorized_sagsbehandlere "
                "WHERE dq_number = :dq_number"),
            {"dq_number": normalized_dq},
        ).fetchone()

    return result is not None


def save_attestation_request(
    payload: dict[str, object],
    attest_types: list[int],
    is_approved: bool,
    database_engine: Engine,
) -> str:
    """Save one row per requested attestation type, regardless of approval.

    :param payload: Validated form payload
    :param attest_types: Parsed attestation types in the form
    :param is_approved: Whether the requesting caseworker is authorized
    :param database_engine: Engine connected to the application database
    :return: Shared request ID for all rows created from the form
    """
    request_id = str(uuid.uuid4())
    requested_at = datetime.datetime.now(datetime.timezone.utc)
    rows = _build_attestation_rows(
        payload=payload,
        request_id=request_id,
        attest_types=attest_types,
        is_approved=is_approved,
        requested_at=requested_at,
    )

    with database_engine.begin() as connection:
        connection.execute(insert(attestation_requests), rows)

    return request_id


def initialize_database(database_engine: Engine) -> None:
    """Create tables.

    :param database_engine: Engine connected to the application database
    """
    with database_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS authorized_sagsbehandlere "
                "(dq_number TEXT PRIMARY KEY)",
            ),
        )
        attestation_requests.create(connection, checkfirst=True)


def _build_attestation_rows(
    payload: dict[str, object],
    request_id: str,
    attest_types: list[int],
    is_approved: bool,
    requested_at: datetime.datetime,
) -> list[dict[str, object]]:
    """Build one database row per selected attestation type.

    :param payload: Validated request body
    :param request_id: Shared identifier for rows from the request
    :param attest_types: Selected attestation type identifiers
    :param is_approved: Whether the requester is authorized
    :param requested_at: Request receipt time in UTC
    :return: Rows ready for insertion into ``attestation_requests``
    :raises ValueError: If required requester, CPR, or subtype data is invalid
    """
    sagsbehandler = payload.get("sagsbehandler")
    requester_dq = extract_sagsbehandler_dq(sagsbehandler)
    requester_name = extract_sagsbehandler_name(sagsbehandler)
    cpr_number = payload.get("medarbejderCPR")
    subtype_entries = payload.get("attestSubType")

    if not requester_dq or not requester_name or not isinstance(
            cpr_number, str):
        raise ValueError(
            "Validated request is missing caseworker or CPR details.")

    if not isinstance(subtype_entries, list):
        raise ValueError(
            "Validated request must contain an attestSubType list.")

    subtype_by_type: dict[int, int] = {}
    for entry in subtype_entries:
        if not isinstance(entry, dict):
            raise ValueError(
                "Validated request contains an invalid subtype entry.")

        selected_type = entry.get("attestType")
        subtype = entry.get("subType")
        if type(selected_type) is not int or type(subtype) is not int:
            raise ValueError(
                "Validated request contains a non-integer subtype.")

        if selected_type in subtype_by_type:
            raise ValueError(
                f"attestType {selected_type} has multiple subtypes.")

        subtype_by_type[selected_type] = subtype

    return [
        {
            "requestId": request_id,
            "rekvirentDQ": requester_dq,
            "rekvirentNavn": requester_name,
            "rekvisitusCPR": cpr_number,
            "attestType": attest_type,
            "attestSubType": subtype_by_type.get(attest_type),
            "erGodkendt": is_approved,
            "erBestilt": False,
            "erModtaget": False,
            "erJournaliseret": False,
            "erSendtTilManuelBehandling": not is_approved,
            "erAdviseret": False,
            "sbsysSagsNr": None,
            "sbsysSagsID": None,
            "anmodetTS": requested_at,
            "bestiltTS": None,
            "modtagetTS": None,
            "journaliseretTS": None,
            "adviseretTS": None,
        }
        for attest_type in attest_types
    ]


def parse_authorized_dq_numbers(csv_content: str) -> set[str]:
    """Parse leader and deputy leader DQ numbers from a semicolon CSV.

    :param csv_content: Decoded administration CSV text
    :return: Unique DQ numbers with an authorized role
    :raises ValueError: If required columns or eligible rows are missing
    """
    dq_numbers: set[str] = set()
    reader = csv.DictReader(StringIO(csv_content), delimiter=";")
    required_columns = {CSV_DQ_COLUMN, CSV_ROLE_COLUMN}
    if not reader.fieldnames or not required_columns.issubset(
            reader.fieldnames):
        raise ValueError(
            "CSV must contain Lokalt brugernavn and Rolle columns.")

    for row in reader:
        # Normalize Danish role text and whitespace before matching.
        role = " ".join(
            (row.get(CSV_ROLE_COLUMN) or "")
            .casefold().replace("æ", "ae").split(),
        )
        dq_number = (row.get(CSV_DQ_COLUMN) or "").strip().upper()
        if role in AUTHORIZED_ROLES and re.fullmatch(
                DQ_NUMBER_PATTERN, dq_number):
            dq_numbers.add(dq_number)

    if not dq_numbers:
        raise ValueError(
            "CSV contains no leder or stedfortraeder for leder DQ numbers.")

    return dq_numbers
