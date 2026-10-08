import pytest

from unittest.mock import patch
from flask import json

from main import create_app


@pytest.fixture()
def app():
    with patch('main.SFTPClient'), patch('main.DatabaseClient'), patch(
            'main.refresh_authorized_dq_numbers'):
        app = create_app()
    app.config.update({
        "TESTING": True,
    })
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def make_payload(**overrides):
    payload = {
        "sagsbehandler": "Fornavn Efternavn - DQ12345",
        "medarbejderCPR": "010190-1234",
        "attestType": "0, 1, 2",
        "attestSubType": [
            {"attestType": 0, "subType": 1},
            {"attestType": 2, "subType": 3},
        ],
        "samtykke": True,
    }
    payload.update(overrides)
    return payload


@patch('api_endpoints.save_attestation_request')
@patch('api_endpoints.is_authorized_sagsbehandler')
def test_receive_data_approved(mock_is_authorized, mock_save, client, app):
    mock_is_authorized.return_value = True
    mock_save.return_value = 'request-id'
    payload = make_payload()

    response = client.post(
        '/api/receive_data', data=json.dumps(payload),
        content_type='application/json')

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "data received",
        "approvalStatus": "approved",
        "requestId": "request-id"}
    engine = app.extensions['database_engine']
    mock_is_authorized.assert_called_once_with('DQ12345', engine)
    mock_save.assert_called_once_with(payload, [0, 1, 2], True, engine)


@patch('api_endpoints.save_attestation_request')
@patch('api_endpoints.is_authorized_sagsbehandler')
def test_receive_data_denied_is_still_saved(
        mock_is_authorized, mock_save, client, app):
    mock_is_authorized.return_value = False
    mock_save.return_value = 'request-id'
    payload = make_payload(attestType="1", attestSubType=[])

    response = client.post(
        '/api/receive_data', data=json.dumps(payload),
        content_type='application/json')

    assert response.status_code == 200
    assert response.get_json()["approvalStatus"] == "denied"
    mock_save.assert_called_once_with(
        payload, [1], False, app.extensions['database_engine'])


@pytest.mark.parametrize("payload", [
    make_payload(attestType="0", attestSubType=[]),
    make_payload(attestType="1", attestSubType=[
        {"attestType": 0, "subType": 1}]),
    make_payload(attestType="0, 0", attestSubType=[
        {"attestType": 0, "subType": 1}]),
    make_payload(attestType="3", attestSubType=[]),
    make_payload(attestType="a"),
    make_payload(medarbejderCPR="0101901234"),
    make_payload(sagsbehandler="Fornavn Efternavn"),
    make_payload(samtykke="true"),
])
@patch('api_endpoints.save_attestation_request')
@patch('api_endpoints.is_authorized_sagsbehandler')
def test_receive_data_invalid_payload(
        mock_is_authorized, mock_save, client, payload):
    response = client.post(
        '/api/receive_data', data=json.dumps(payload),
        content_type='application/json')

    assert response.status_code == 400
    assert response.get_json()["errors"]
    mock_is_authorized.assert_not_called()
    mock_save.assert_not_called()


@pytest.mark.parametrize(
        "field", [
            "sagsbehandler",
            "medarbejderCPR",
            "attestType",
            "attestSubType",
            "samtykke"])
@patch('api_endpoints.save_attestation_request')
def test_receive_data_missing_field(mock_save, client, field):
    payload = make_payload()
    del payload[field]

    response = client.post(
        '/api/receive_data', data=json.dumps(payload),
        content_type='application/json')

    assert response.status_code == 400
    assert f"Missing required field: {field}." in response.get_json()["errors"]
    mock_save.assert_not_called()


def test_receive_data_not_json_object(client):
    response = client.post(
        '/api/receive_data', data='test data',
        content_type='text/plain')
    assert response.status_code == 400

    response = client.post(
        '/api/receive_data', data=json.dumps([1, 2]),
        content_type='application/json')
    assert response.status_code == 400


def test_receive_data_no_database(client, app):
    app.extensions['database_engine'] = None

    response = client.post(
        '/api/receive_data', data=json.dumps(make_payload()),
        content_type='application/json')

    assert response.status_code == 503


@patch('api_endpoints.example')
def test_example_endpoint(mock_example, client):
    # Test POST with JSON data
    mock_example.return_value = 'You posted: {"test": "data"}'
    response = client.post(
        '/api/example', data=json.dumps({"test": "data"}),
        content_type='application/json')
    assert response.status_code == 200
    assert response.data == b"You posted: {'test': 'data'}"

    # Test POST with non-JSON data
    mock_example.return_value = 'Content-Type must be application/json'
    response = client.post(
        '/api/example', data='test data',
        content_type='text/plain')
    assert response.status_code == 400
    assert response.data == b'Content-Type must be application/json'

    # Test GET
    response = client.get('/api/example')
    assert response.status_code == 200
    assert response.data == b'Example response'
