import pytest

from attest_validation import (extract_sagsbehandler_dq,
                               extract_sagsbehandler_name,
                               parse_attest_types,
                               validate_attest_request,
                               validate_attest_types,
                               validate_json_structure)


def make_payload(**overrides):
    payload = {
        "sagsbehandler": "Fornavn Efternavn - DQ00000",
        "medarbejderCPR": "010190-1234",
        "attestSubType": [],
        "samtykke": True,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("value, expected", [
    ("0", [0]),
    ("0, 1", [0, 1]),
    ("0,1,2", [0, 1, 2]),
    (2, [2]),
])
def test_parse_attest_types_valid(value, expected):
    assert parse_attest_types(value) == (expected, [])


@pytest.mark.parametrize("value", ["", "0,", "a", "1.5", True, None, [0]])
def test_parse_attest_types_invalid(value):
    types, errors = parse_attest_types(value)
    assert types == []
    assert errors


def test_validate_attest_types():
    assert validate_attest_types([0, 1, 2], {0, 1, 2}) == []
    assert validate_attest_types([], {0, 1, 2})
    assert validate_attest_types([0, 0], {0, 1, 2})
    assert validate_attest_types([3], {0, 1, 2})


def test_validate_json_structure():
    assert validate_json_structure({"a": 1}, ["a"]) == []
    assert validate_json_structure({}, ["a", "b"]) == [
        "Missing required field: a.", "Missing required field: b."]


@pytest.mark.parametrize("value, dq, name", [
    ("Fornavn Efternavn - DQ00000", "DQ00000", "Fornavn Efternavn"),
    ("Fornavn Efternavn - dq54321", "DQ54321", "Fornavn Efternavn"),
    ("Fornavn Mellem Efternavn -DQ12345", "DQ12345",
     "Fornavn Mellem Efternavn"),
])
def test_extract_sagsbehandler(value, dq, name):
    assert extract_sagsbehandler_dq(value) == dq
    assert extract_sagsbehandler_name(value) == name


@pytest.mark.parametrize("value", [
    "Fornavn Efternavn", "- DQ00000", "Navn - DQ0000", "Navn - DQ000000",
    "Navn - DQB6106", "Navn - XX00000", None, 123,
])
def test_extract_sagsbehandler_invalid(value):
    assert extract_sagsbehandler_dq(value) is None
    assert extract_sagsbehandler_name(value) is None


@pytest.mark.parametrize("attest_types, subtypes", [
    ([0], [{"attestType": 0, "subType": 1}]),
    ([0, 1], [{"attestType": 0, "subType": 1}]),
    ([0, 1, 2], [
        {"attestType": 0, "subType": 1}, {"attestType": 2, "subType": 2}]),
    ([1], []),
])
def test_validate_attest_request_valid_combinations(attest_types, subtypes):
    assert validate_attest_request(
        make_payload(attestSubType=subtypes), attest_types) == []


@pytest.mark.parametrize("attest_types, subtypes", [
    ([0], []),
    ([0, 2], [{"attestType": 0, "subType": 1}]),
    ([1], [{"attestType": 1, "subType": 1}]),
    ([1], [{"attestType": 0, "subType": 1}]),
    ([0], [{"attestType": 0, "subType": 1}, {"attestType": 0, "subType": 2}]),
    ([0], [{"attestType": 0, "subType": "1"}]),
    ([0], [{"attestType": "0", "subType": 1}]),
    ([0], ["not a dict"]),
    ([1], "not a list"),
])
def test_validate_attest_request_invalid_subtypes(attest_types, subtypes):
    assert validate_attest_request(
        make_payload(attestSubType=subtypes), attest_types)


@pytest.mark.parametrize("overrides", [
    {"medarbejderCPR": "0101901234"},
    {"medarbejderCPR": 101901234},
    {"sagsbehandler": "Fornavn Efternavn"},
    {"samtykke": "true"},
    {"samtykke": 1},
])
def test_validate_attest_request_invalid_fields(overrides):
    assert validate_attest_request(make_payload(**overrides), [1])
