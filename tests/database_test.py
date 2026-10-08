import pytest
from unittest.mock import patch, MagicMock
from utils.database import DatabaseClient
from attest_database import (initialize_database,
                             is_authorized_sagsbehandler,
                             parse_authorized_dq_numbers,
                             refresh_authorized_dq_numbers,
                             save_attestation_request)


CSV_CONTENT = (
    "Navn;Lokalt brugernavn;Rolle\n"
    "Leder Person;dq00001;Leder\n"
    "Stedfortræder Person;DQ00002;Stedfortræder for leder\n"
    "Forkert Format;DQB6106;Leder\n"
    "Almindelig Medarbejder;DQ00003;Medarbejder\n"
    "Ugyldig;XX00004;Leder\n"
)


def test_invalid_db_type():
    with pytest.raises(ValueError) as excinfo:
        DatabaseClient(
            'invalid_db', 'database',
            'username', 'password', 'host')
    assert 'Invalid database type' in str(excinfo.value)


@patch('sqlalchemy.create_engine')
def test_valid_db_type_mssql(mock_create_engine):
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine

    client = DatabaseClient(
        'mssql', 'database', 'username', 'password', 'host')
    mock_create_engine.assert_called_with(
        'mssql+pymssql://username:password@host/database')

    client = DatabaseClient(
        'mariadb', 'database', 'username', 'password', 'host', 3306)
    mock_create_engine.assert_called_with(
        'mariadb+mariadbconnector://username:password@host:3306/database')

    client = DatabaseClient(
        'postgresql', 'database', 'username', 'password', 'host', '5432')
    mock_create_engine.assert_called_with(
        'postgresql+psycopg2://username:password@host:5432/database')
    assert client.engine == mock_engine


@patch('sqlalchemy.create_engine')
def test_get_connection_success(mock_create_engine):
    mock_engine = MagicMock()
    mock_connection = MagicMock()
    mock_engine.connect.return_value = mock_connection
    mock_create_engine.return_value = mock_engine

    client = DatabaseClient(
        'mssql', 'database', 'username', 'password', 'host')
    conn = client.get_connection()
    assert conn == mock_connection
    mock_engine.connect.assert_called_once()


@patch('sqlalchemy.create_engine')
def test_get_connection_failure(mock_create_engine):
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = Exception('Connection error')
    mock_create_engine.return_value = mock_engine

    client = DatabaseClient(
        'mssql', 'database', 'username', 'password', 'host')
    with patch.object(client.logger, 'error') as mock_logger_error:
        conn = client.get_connection()
        assert conn is None
        mock_logger_error.assert_called_with(
            'Error connecting to database: Connection error')


@patch('sqlalchemy.create_engine')
def test_get_connection_no_engine_failure(mock_create_engine):
    client = DatabaseClient(
        'mssql', 'database', 'username', 'password', 'host')
    client.engine = None
    with patch.object(client.logger, 'error') as mock_logger_error:
        conn = client.get_connection()
        assert conn is None
        mock_logger_error.assert_called_with(
            'DatabaseClient not initialized properly. '
            'Engine is None. Check error from init.')


@patch('sqlalchemy.create_engine')
def test_execute_sql_success(mock_create_engine):
    mock_engine = MagicMock()
    mock_connection = MagicMock()
    mock_result = MagicMock()
    mock_connection.__enter__().execute.return_value = mock_result
    mock_engine.connect.return_value = mock_connection
    mock_create_engine.return_value = mock_engine

    client = DatabaseClient(
        'mssql', 'database', 'username', 'password', 'host')
    sql = 'SELECT * FROM table'
    result = client.execute_sql(sql)
    assert result == mock_result


@patch('sqlalchemy.create_engine')
def test_execute_sql_failure(mock_create_engine):
    mock_engine = MagicMock()
    mock_connection = MagicMock()
    mock_connection.__enter__().execute.side_effect = Exception('SQL error')
    mock_engine.connect.return_value = mock_connection
    mock_create_engine.return_value = mock_engine

    client = DatabaseClient(
        'mssql', 'database', 'username', 'password', 'host')
    sql = 'SELECT * FROM table'
    with patch.object(client.logger, 'error') as mock_logger_error:
        result = client.execute_sql(sql)
        assert result is None
        mock_logger_error.assert_any_call('Error executing SQL: SQL error')


def test_parse_authorized_dq_numbers():
    assert parse_authorized_dq_numbers(CSV_CONTENT) == {'DQ00001', 'DQ00002'}


@pytest.mark.parametrize('content', [
    '',
    'Navn;Rolle\nA;Leder\n',
    'Lokalt brugernavn;Rolle\nDQ00003;Medarbejder\n',
])
def test_parse_authorized_dq_numbers_invalid(content):
    with pytest.raises(ValueError):
        parse_authorized_dq_numbers(content)


@patch('attest_database.initialize_database')
def test_refresh_authorized_dq_numbers(mock_initialize):
    mock_engine = MagicMock()
    mock_connection = mock_engine.begin.return_value.__enter__.return_value

    assert refresh_authorized_dq_numbers(CSV_CONTENT, mock_engine) == 2

    mock_initialize.assert_called_once_with(mock_engine)
    assert mock_connection.execute.call_count == 2
    assert 'DELETE' in str(mock_connection.execute.call_args_list[0][0][0])
    assert mock_connection.execute.call_args_list[1][0][1] == [
        {'dq_number': 'DQ00001'}, {'dq_number': 'DQ00002'}]


@patch('attest_database.initialize_database')
def test_refresh_authorized_dq_numbers_invalid_csv_keeps_list(mock_initialize):
    mock_engine = MagicMock()

    with pytest.raises(ValueError):
        refresh_authorized_dq_numbers('Lokalt brugernavn;Rolle\n', mock_engine)

    mock_initialize.assert_not_called()
    mock_engine.begin.assert_not_called()


def test_is_authorized_sagsbehandler():
    mock_engine = MagicMock()
    mock_connection = mock_engine.connect.return_value.__enter__.return_value

    mock_connection.execute.return_value.fetchone.return_value = (1,)
    assert is_authorized_sagsbehandler(' dq00002 ', mock_engine) is True
    assert mock_connection.execute.call_args[0][1] == {'dq_number': 'DQ00002'}

    mock_connection.execute.return_value.fetchone.return_value = None
    assert is_authorized_sagsbehandler('DQ00003', mock_engine) is False


def test_save_attestation_request():
    mock_engine = MagicMock()
    mock_connection = mock_engine.begin.return_value.__enter__.return_value
    payload = {
        'sagsbehandler': 'Fornavn Efternavn - DQ12345',
        'medarbejderCPR': '010190-1234',
        'attestType': '0, 1, 2',
        'attestSubType': [
            {'attestType': 0, 'subType': 5}, {'attestType': 2, 'subType': 7}],
        'samtykke': True,
    }

    request_id = save_attestation_request(
        payload, [0, 1, 2], False, mock_engine)

    rows = mock_connection.execute.call_args[0][1]
    assert [(row['attestType'], row['attestSubType']) for row in rows] == [
        (0, 5), (1, None), (2, 7)]
    for row in rows:
        assert row['requestId'] == request_id
        assert row['rekvirentDQ'] == 'DQ12345'
        assert row['rekvirentNavn'] == 'Fornavn Efternavn'
        assert row['rekvisitusCPR'] == '010190-1234'
        assert row['erGodkendt'] is False
        assert row['erSendtTilManuelBehandling'] is True
        assert row['erBestilt'] is False
        assert row['anmodetTS'] is not None
        assert row['bestiltTS'] is None


@patch('attest_database.attestation_requests')
def test_initialize_database_creates_tables(mock_table):
    mock_engine = MagicMock()
    mock_connection = mock_engine.begin.return_value.__enter__.return_value

    initialize_database(mock_engine)

    assert 'authorized_sagsbehandlere' in str(
        mock_connection.execute.call_args_list[0][0][0])
    mock_table.create.assert_called_once_with(mock_connection, checkfirst=True)
