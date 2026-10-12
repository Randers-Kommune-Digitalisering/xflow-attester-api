import importlib
import os
import sys
from collections.abc import Iterator
from unittest import mock

import pytest
import sqlalchemy
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("FLASK_ENV", "dev")

AUTHORIZATION_CSV = "Lokalt brugernavn;Rolle\nDQ12345;Leder\nDQ54321;Medarbejder\n"


@pytest.fixture()
def app() -> Iterator[Flask]:
    engine = sqlalchemy.create_engine("sqlite://", poolclass=StaticPool)
    sftp_connection = mock.MagicMock()
    sftp_file = sftp_connection.open.return_value.__enter__.return_value
    sftp_file.read.return_value = AUTHORIZATION_CSV.encode("utf-16")

    with mock.patch("utils.sftp.SFTPClient") as sftp_client, mock.patch("rkdigi.DatabaseManager") as database_manager:
        sftp_client.return_value.get_connection.return_value = sftp_connection
        database_manager.return_value.get_session = sessionmaker(bind=engine)
        # main builds the WSGI app on import, so it must be (re)imported while mocks are active.
        sys.modules.pop("main", None)
        model = importlib.import_module("model")
        model.Base.metadata.create_all(engine)
        main = importlib.import_module("main")
        app = main.create_app()

    app.config.update({
        "TESTING": True,
    })

    yield app
    engine.dispose()


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()


def test_healthz(client: FlaskClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_metrics(client: FlaskClient) -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"http_server_errors_total" in response.data


@pytest.mark.parametrize("sagsbehandler, approval_status, is_approved", [
    ("Fornavn Efternavn - DQ12345", "approved", True),
    ("Fornavn Efternavn - DQ54321", "denied", False),
])
def test_receive_data_saves_request(
    app: Flask,
    client: FlaskClient,
    sagsbehandler: str,
    approval_status: str,
    is_approved: bool,
) -> None:
    response = client.post("/api/receive_data", json=make_payload(sagsbehandler))

    assert response.status_code == 200
    body = response.get_json()
    assert body["approvalStatus"] == approval_status

    engine = app.extensions["database_manager"].get_session.kw["bind"]
    with engine.connect() as connection:
        request_row = connection.execute(
            sqlalchemy.text(
                "SELECT subject_cpr, is_approved FROM attestation_request WHERE request_id = :request_id",
            ),
            {"request_id": body["requestId"]},
        ).one()
        order_rows = connection.execute(
            sqlalchemy.text(
                "SELECT o.attest_type, o.attest_subtype, o.status, e.status "
                "FROM attestation_order o JOIN order_event e ON e.order_id = o.order_id "
                "WHERE o.request_id = :request_id ORDER BY o.attest_type",
            ),
            {"request_id": body["requestId"]},
        ).all()

    expected_status = "pending_order" if is_approved else "rejected"
    assert tuple(request_row) == ("0101901234", is_approved)
    assert [tuple(row) for row in order_rows] == [
        (0, 1, expected_status, expected_status),
        (1, None, expected_status, expected_status),
    ]


def test_receive_data_rejects_invalid_payload(client: FlaskClient) -> None:
    response = client.post("/api/receive_data", json={"attestType": "0"})
    assert response.status_code == 400
    assert response.get_json()["errors"]


@pytest.mark.parametrize("cpr", ["010190-1234", "0101901234"])
def test_receive_data_stores_cpr_without_hyphen(app: Flask, client: FlaskClient, cpr: str) -> None:
    payload = make_payload("Fornavn Efternavn - DQ12345")
    payload["medarbejderCPR"] = cpr
    response = client.post("/api/receive_data", json=payload)

    assert response.status_code == 200
    engine = app.extensions["database_manager"].get_session.kw["bind"]
    with engine.connect() as connection:
        stored_cpr = connection.execute(
            sqlalchemy.text("SELECT subject_cpr FROM attestation_request WHERE request_id = :request_id"),
            {"request_id": response.get_json()["requestId"]},
        ).scalar_one()

    assert stored_cpr == "0101901234"


def make_payload(sagsbehandler: str) -> dict[str, object]:
    return {
        "sagsbehandler": sagsbehandler,
        "medarbejderCPR": "010190-1234",
        "attestType": "0, 1",
        "attestSubType": [{"attestType": 0, "subType": 1}],
        "samtykke": True,
    }
