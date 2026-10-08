import pytest
from unittest.mock import patch
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


def test_healthz(client):
    response = client.get('/healthz')
    assert response.status_code == 200
    assert response.get_json()['status'] == 'ok'


def test_metrics(client):
    response = client.get('/metrics')
    assert response.status_code == 200
    assert 'http_server_errors' in response.text


@patch('main.refresh_authorized_dq_numbers')
@patch('main.DatabaseClient')
@patch('main.SFTPClient')
def test_create_app_loads_authorization_csv(
        mock_sftp_client, mock_database_client, mock_refresh):
    mock_connection = mock_sftp_client.return_value.get_connection.return_value
    mock_file = mock_connection.open.return_value.__enter__.return_value
    mock_file.read.return_value = 'Lokalt brugernavn;Rolle\n'.encode('utf-16')

    app = create_app()

    mock_connection.open.assert_called_once_with(
        '/Brugeradministration-da.csv', 'rb')
    mock_connection.close.assert_called_once()
    engine = mock_database_client.return_value.engine
    mock_refresh.assert_called_once_with('Lokalt brugernavn;Rolle\n', engine)
    assert app.extensions['database_engine'] is engine


@patch('main.DatabaseClient')
@patch('main.SFTPClient')
def test_create_app_sftp_unavailable(mock_sftp_client, mock_database_client):
    mock_sftp_client.return_value.get_connection.return_value = None

    with pytest.raises(RuntimeError):
        create_app()

    mock_database_client.assert_not_called()


@patch('main.refresh_authorized_dq_numbers')
@patch('main.DatabaseClient')
@patch('main.SFTPClient')
def test_server_errors_are_counted(mock_sftp_client, mock_database_client, mock_refresh):
    app = create_app()

    @app.get('/fail')
    def fail():
        return 'error', 500

    with patch('main.error_counter') as mock_error_counter:
        response = app.test_client().get('/fail')

    assert response.status_code == 500
    mock_error_counter.labels.assert_called_once_with(
        endpoint='/fail', status='500')
    mock_error_counter.labels.return_value.inc.assert_called_once()
