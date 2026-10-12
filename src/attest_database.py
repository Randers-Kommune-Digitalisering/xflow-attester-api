"""Database access for authorized caseworkers and submitted forms."""

import csv
import datetime
import uuid
from io import StringIO

from rkdigi import DatabaseManager
from sqlalchemy import delete

from attest_validation import (extract_sagsbehandler_dq,
                               extract_sagsbehandler_name)
from model import (AttestationOrder, AttestationRequest,
                   AuthorizedSagsbehandler, OrderEvent, OrderStatus,
                   SagsbehandlerRoles)

CSV_DQ_COLUMN = "Lokalt brugernavn"
CSV_ROLE_COLUMN = "Rolle"
AUTHORIZED_ROLES = {
    "leder": SagsbehandlerRoles.LEDER,
    "stedfortraeder for leder": SagsbehandlerRoles.STEDFORTRAEDER,
}


def refresh_authorized_dq_numbers(
    csv_content: str,
    database_manager: DatabaseManager,
) -> int:
    """Replace authorized caseworkers with entries from the CSV.

    :param csv_content: administration CSV content as a string
    :param database_manager: Manager connected to the application database
    :return: Number of unique authorized DQ numbers
    """
    # Validate the file before opening the transaction
    # Bad input cannot clear the list.
    roles_by_dq = parse_authorized_dq_numbers(csv_content)

    # Keep the full replacement atomic
    # A failed insert rolls back the deletion.
    with database_manager.get_session() as session, session.begin():
        session.execute(delete(AuthorizedSagsbehandler))
        session.add_all(
            AuthorizedSagsbehandler(dq_number=dq_number, role=role)
            for dq_number, role in sorted(roles_by_dq.items())
        )

    return len(roles_by_dq)


def is_authorized_sagsbehandler(
        dq_number: str, database_manager: DatabaseManager) -> bool:
    """Check whether a DQ number belongs to a leader or deputy leader.

    :param dq_number: DQ number extracted from the form
    :param database_manager: Manager connected to the application database
    :return: True if the DQ number is authorized
    """
    normalized_dq = dq_number.strip().upper()
    with database_manager.get_session() as session:
        return session.get(AuthorizedSagsbehandler, normalized_dq) is not None


def save_attestation_request(
    payload: dict[str, object],
    attest_types: list[int],
    is_approved: bool,
    database_manager: DatabaseManager,
) -> str:
    """Save the request with one order per attestation type.

    Unapproved requests are saved with rejected orders.

    :param payload: Validated form payload
    :param attest_types: Parsed attestation types in the form
    :param is_approved: Whether the requesting caseworker is authorized
    :param database_manager: Manager connected to the application database
    :return: ID of the saved request
    """
    attestation_request = _build_attestation_request(
        payload=payload,
        attest_types=attest_types,
        is_approved=is_approved,
        requested_at=datetime.datetime.now(datetime.timezone.utc),
    )
    # Read before commit; the instance is expired and detached afterwards.
    request_id = attestation_request.request_id

    with database_manager.get_session() as session, session.begin():
        session.add(attestation_request)

    return request_id


def _build_attestation_request(
    payload: dict[str, object],
    attest_types: list[int],
    is_approved: bool,
    requested_at: datetime.datetime,
) -> AttestationRequest:
    """Build a request with one order and initial event per attestation type.

    :param payload: Validated request body
    :param attest_types: Selected attestation type identifiers
    :param is_approved: Whether the requester is authorized
    :param requested_at: Request receipt time in UTC
    :return: Request ready to be added to a session
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

    status = OrderStatus.PENDING_ORDER if is_approved else OrderStatus.REJECTED
    return AttestationRequest(
        request_id=str(uuid.uuid4()),
        requester_dq=requester_dq,
        requester_name=requester_name,
        subject_cpr=cpr_number.replace("-", ""),
        is_approved=is_approved,
        requested_at=requested_at,
        orders=[
            AttestationOrder(
                attest_type=attest_type,
                attest_subtype=subtype_by_type.get(attest_type),
                status=status,
                events=[
                    OrderEvent(
                        status=status,
                        occurred_at=requested_at,
                        actor=requester_dq,
                    ),
                ],
            )
            for attest_type in attest_types
        ],
    )


def parse_authorized_dq_numbers(
        csv_content: str) -> dict[str, SagsbehandlerRoles]:
    """Parse leader and deputy leader DQ numbers from a semicolon CSV.

    :param csv_content: Decoded administration CSV text
    :return: Authorized role per unique DQ number
    :raises ValueError: If required columns or eligible rows are missing
    """
    roles_by_dq: dict[str, SagsbehandlerRoles] = {}
    reader = csv.DictReader(StringIO(csv_content), delimiter=";")
    required_columns = {CSV_DQ_COLUMN, CSV_ROLE_COLUMN}
    if not reader.fieldnames or not required_columns.issubset(
            reader.fieldnames):
        raise ValueError(
            "CSV must contain Lokalt brugernavn and Rolle columns.")

    for row in reader:
        # Normalize Danish role text and whitespace before matching.
        role_text = " ".join(
            (row.get(CSV_ROLE_COLUMN) or "")
            .casefold().replace("æ", "ae").split(),
        )
        role = AUTHORIZED_ROLES.get(role_text)
        dq_number = (row.get(CSV_DQ_COLUMN) or "").strip().upper()
        if role is None or not dq_number:
            continue

        # A user listed with both roles is stored as leder.
        if roles_by_dq.get(dq_number) != SagsbehandlerRoles.LEDER:
            roles_by_dq[dq_number] = role

    if not roles_by_dq:
        raise ValueError(
            "CSV contains no leder or stedfortraeder for leder DQ numbers.")

    return roles_by_dq
