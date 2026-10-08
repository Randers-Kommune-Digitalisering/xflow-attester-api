"""Validation helpers for incoming attestation requests."""

import re

REQUIRED_ATTEST_REQUEST_FIELDS = [
    "sagsbehandler",
    "medarbejderCPR",
    "attestType",
    "attestSubType",
    "samtykke",
]
VALID_ATTEST_TYPES = {0, 1, 2}
DQ_NUMBER_PATTERN = r"DQ[0-9]{5}"
# TODO: Replace the empty sets with X-Flow's allowed subtype codes
VALID_SUBTYPES_BY_TYPE: dict[int, set[int]] = {
    0: set(),
    2: set(),
}


def parse_attest_types(value: object) -> tuple[list[int], list[str]]:
    """
    Parse an integer or comma-separated attestType value.

    :param value: raw value from the request JSON
    :return: parsed types and a list of error messages if any
    """
    if isinstance(value, bool):
        return [], ["attestType must be an int or comma-separated string."]

    if isinstance(value, int):
        values = [str(value)]
    elif isinstance(value, str):
        values = value.split(",")
    else:
        return [], ["attestType must be an int or comma-separated string."]

    if any(not item.strip() for item in values):
        return [], ["attestType must not be empty."]

    try:
        return [int(item.strip()) for item in values], []
    except ValueError:
        return [], ["attestType must contain only integers."]


def validate_attest_request(
    payload: dict[str, object],
    attest_types: list[int],
) -> list[str]:
    """
    Validate the request fields and rules relating types to subtypes.

    :param payload: the incoming request payload
    :param attest_types: the parsed attest types from the request
    :return: a list of error messages if any
    """
    errors: list[str] = []
    if extract_sagsbehandler_dq(payload.get("sagsbehandler")) is None:
        errors.append(
            "sagsbehandler must end with a name and DQ number, "
            "e.g. Name - DQ0000.")

    medarbejder_cpr = payload.get("medarbejderCPR")
    if not isinstance(medarbejder_cpr, str):
        errors.append("medarbejderCPR must be a string.")
    elif re.fullmatch(r"[0-9]{6}-[0-9]{4}", medarbejder_cpr) is None:
        errors.append("medarbejderCPR must be formatted as DDMMYY-XXXX.")

    if type(payload.get("samtykke")) is not bool:
        errors.append("samtykke must be a boolean.")

    subtypes = payload.get("attestSubType")
    if not isinstance(subtypes, list):
        return errors + ["attestSubType must be a list."]

    found_types: set[int] = set()
    for index, subtype_entry in enumerate(subtypes):
        if not isinstance(subtype_entry, dict):
            errors.append(f"attestSubType entry {index} must be a dictionary.")
            continue

        selected_type = subtype_entry.get("attestType")
        subtype = subtype_entry.get("subType")
        if type(selected_type) is not int:
            errors.append(f"attestSubType entry {index} is not an integer.")
            continue

        if selected_type not in (0, 2):
            errors.append(
                f"attestSubType entry {index} "
                f"may only refer to attestType 0 or 2.",
            )
            continue

        if selected_type not in attest_types:
            errors.append(f"attestSubType item {index} "
                          f"refers to an unselected attestType.")
            continue

        if selected_type in found_types:
            errors.append(f"attestType {selected_type} "
                          f"can have at most one subtype.")
            continue

        if type(subtype) is not int:
            errors.append(f"attestSubType entry {index} "
                          f"subType must be an integer.")
            continue

        allowed_subtypes = VALID_SUBTYPES_BY_TYPE.get(selected_type)
        if allowed_subtypes and subtype not in allowed_subtypes:
            errors.append(f"attestSubType entry {index} "
                          f"has an invalid subtype.")
            continue

        found_types.add(selected_type)

    for selected_type in (0, 2):
        if selected_type in attest_types and selected_type not in found_types:
            errors.append(
                f"attestType {selected_type} requires an attestSubType.")

    return errors


def validate_json_structure(
        payload: dict[str, object],
        required_keys: list[str]) -> list[str]:
    """Report required keys missing from a parsed JSON object.

    :param payload: Parsed request JSON
    :param required_keys: Keys that must be present
    :return: Error messages, or an empty list when all keys are present
    """
    return [f"Missing required field: {key}."
            for key in required_keys if key not in payload]


def validate_attest_types(
        attest_types: list[int],
        valid_types: set[int]) -> list[str]:
    """Validate attestation types against supported identifiers.

    :param attest_types: Parsed attestation type identifiers
    :param valid_types: Supported identifiers
    :return: Error messages, or an empty list when all values are valid
    """
    errors: list[str] = []
    if not attest_types:
        errors.append("attestType must contain at least one type.")

    if len(attest_types) != len(set(attest_types)):
        errors.append("attestType must not contain duplicate types.")

    if any(type(value) is not int or value not in valid_types for value in attest_types):
        errors.append("attestType contains invalid types.")

    return errors


def extract_sagsbehandler_dq(value: object) -> str | None:
    """
    Extract the trailing DQ number from the displayed caseworker name.

    :param value: Caseworker field, e.g. "Fornavn Efternavn - DQ0000"
    :return: Uppercase DQ number, or None if the format is invalid
    """
    match = _match_sagsbehandler(value)
    return match.group(2).upper() if match else None


def extract_sagsbehandler_name(value: object) -> str | None:
    """
    Extract the caseworker name from the displayed caseworker field.

    :param value: Caseworker field, e.g. "Fornavn Efternavn - DQ0000"
    :return: Name portion, or None if the format is invalid
    """
    match = _match_sagsbehandler(value)
    return match.group(1).strip() if match else None


def _match_sagsbehandler(value: object) -> re.Match[str] | None:
    if not isinstance(value, str):
        return None

    return re.fullmatch(
        rf"(.+)\s+-\s*({DQ_NUMBER_PATTERN})",
        value.strip(), re.IGNORECASE)
