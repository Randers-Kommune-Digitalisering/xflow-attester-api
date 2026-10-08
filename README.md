# xflow-attester-api
API der modtager attestbestillinger (straffeattest, børneattest m.fl.) fra X-Flow, validerer dem, kontrollerer at rekvirenten er leder/stedfortræder og gemmer bestillingen i databasen.

## Dataflow
```mermaid
flowchart LR
    XF[X-Flow formular] -- POST JSON --> API[/api/receive_data/]
    SFTP[(SFTP: Brugeradministration-da.csv)] -- ved opstart --> APP[xflow-attester-api]
    API --> APP
    APP -- autoriserede DQ-numre + bestillinger --> DB[(MSSQL)]
```
1. **Ved opstart** hentes `/Brugeradministration-da.csv` (semikolon-separeret) fra SFTP. DQ-numre med rollen *Leder* eller *Stedfortræder for leder* gemmes i tabellen `authorized_sagsbehandlere` (listen erstattes hver gang). Kan SFTP ikke nås, starter app'en ikke.
2. **Ved modtagelse** valideres JSON, rekvirentens DQ-nummer slås op, og der oprettes **én række pr. bestilt attestType** i `attestation_requests`.
3. Bestillinger fra ikke-autoriserede rekvirenter gemmes også, men med `erGodkendt = false` og `erSendtTilManuelBehandling = true`.

> Data indeholder CPR-numre (personfølsomme oplysninger). Brug aldrig produktionsdata i test, og log ikke payloads.

## Endpoints
| Metode | Sti | Beskrivelse |
|---|---|---|
| POST | `/api/receive_data` | Modtager bestilling fra X-Flow |
| GET | `/healthz` | Health check – returnerer `{"status": "ok"}` |
| GET | `/metrics` | Prometheus metrics (bl.a. `http_server_errors_total`) |

### POST /api/receive_data
```json
{
    "sagsbehandler": "Fornavn Efternavn - DQ12345",
    "medarbejderCPR": "010190-1234",
    "attestType": "0, 1, 2",
    "attestSubType": [
        {"attestType": 0, "subType": 1},
        {"attestType": 2, "subType": 3}
    ],
    "samtykke": true
}
```
Valideringsregler:
* `sagsbehandler`: `Navn - DQ` + præcis 5 cifre.
* `medarbejderCPR`: `DDMMÅÅ-XXXX`.
* `attestType`: `0`, `1` og/eller `2` – int eller kommasepareret string, ingen dubletter.
* `attestSubType`: præcis ét objekt for hver bestilt attestType 0 og 2. AttestType 1 har ingen subtype (`[]` hvis kun 1 er bestilt).
* `samtykke`: boolean.

Svar:
* `200` – `{"status": "data received", "approvalStatus": "approved" | "denied", "requestId": "<uuid>"}`
* `400` – `{"errors": [...]}` ved valideringsfejl
* `503` – database ikke konfigureret

### Tabel `attestation_requests`
Primærnøgle: (`requestId`, `attestType`). Felter: `rekvirentDQ`, `rekvirentNavn`, `rekvisitusCPR`, `attestType`, `attestSubType`, `erGodkendt`, `erBestilt`, `erModtaget`, `erJournaliseret`, `erSendtTilManuelBehandling`, `erAdviseret`, `sbsysSagsNr`, `sbsysSagsID`, `anmodetTS`, `bestiltTS`, `modtagetTS`, `journaliseretTS`, `adviseretTS`.

Tabellerne oprettes automatisk ved opstart.

## Konfiguration
Miljøvariabler (secrets ligger i Bitwarden). Lokalt lægges de i en `.env` fil i projektets rod – den er git-ignored og må **aldrig** committes.

| Variabel | Beskrivelse |
|---|---|
| `DEBUG` | `True`/`False` |
| `PORT` | Port app'en lytter på (default `8080`) |
| `ATTEST_DB_TYPE` | `mssql`, `mariadb` eller `postgresql` (default `mssql`) |
| `ATTEST_DB_HOST` / `ATTEST_DB_PORT` | Database server |
| `ATTEST_DB_NAME` | Databasenavn |
| `ATTEST_DB_USERNAME` / `ATTEST_DB_PASSWORD` | Database login |
| `SFTP_HOST` / `SFTP_USERNAME` | SFTP server (SFTP-SDRoller) |
| `SFTP_PASSWORD` | SFTP kodeord – eller brug nøgle herunder |
| `SFTP_KEY_BASE64` / `SFTP_KEY_PASS` | Base64-kodet SSH nøgle og evt. kodeord (valgfri) |

## Udvikling
### Opsætning
* Windows: `setup-dev-windows.cmd` – Linux/Codespace: `. ./setup-dev-linux.sh`
* Scripts opretter `.venv` og installerer `src/requirements.txt` og `requirements-dev.txt`.

### Almindelige commands
* Start app'en: `python src/main.py`
* Start i docker: `docker compose up --build` (læser `.env`)
* Unit tests: `pytest` (eksterne systemer mockes – kræver ikke SFTP/DB)
* Lint: `flake8 --ignore=E501 src tests --show-source`

### Projektstruktur
* [src/main.py](src/main.py) – opretter Flask app, henter autorisationsliste fra SFTP, forbinder til DB
* [src/api_endpoints.py](src/api_endpoints.py) – `/api/receive_data`
* [src/attest_validation.py](src/attest_validation.py) – validering af payload
* [src/attest_database.py](src/attest_database.py) – tabeller, autorisationsliste og lagring af bestillinger
* [src/utils/](src/utils/) – config, logging/metrics, database-, SFTP- og API-klienter

### Kendte begrænsninger / TODO
* Gyldige subtype-koder er ikke fastlagt endnu (`VALID_SUBTYPES_BY_TYPE` i [attest_validation.py](src/attest_validation.py)).
* Autorisationslisten opdateres kun ved opstart.


### Logning
* Logning gøres med logger og **ikke** print() functionen
```
import logging
logger = logging.getLogger(__name__)
logger.info('My log line')
```
* Logning til stdout med filtrering (kald til /healthz og /metrics fjernes) er sat op i [logging.py](src/utils/logging.py) og kaldes fra [main.py](src/main.py)

### Database
* DatabaseClient kan håndtere 3 typer af databaser: 'mariadb', 'postgresql' og 'mssql'
* Kan returnere en connection eller køre sql, som returnerer et [SQLAlchemy Result object](https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.Result)
* Eksempel på brug:
```
from utils.config import ATTEST_DB_TYPE, ATTEST_DB_NAME, ATTEST_DB_USERNAME, ATTEST_DB_PASSWORD, ATTEST_DB_HOST, ATTEST_DB_PORT
from utils.database import DatabaseClient

my_db = DatabaseClient(ATTEST_DB_TYPE, ATTEST_DB_NAME, ATTEST_DB_USERNAME, ATTEST_DB_PASSWORD, ATTEST_DB_HOST, ATTEST_DB_PORT)

res = my_db.execute_sql('SELECT * FROM my_table')
for row in res:
    print(row)
```

### HTTP(S) requests - brug af eksterne API'er
APIClient kan håntere flere typer authentication, eksempel på brug herunder:
* API key, fx. uddannelsesstatistik
```
from utils.config import MY_API_KEY
from utils.api_requests import APIClient

us_client = ApiClient('https://api.uddannelsesstatistik.dk/Api/v1/statistik', api_key=MY_API_KEY)
```
* Access token, fx. sbsys eller nexus
```
from utils.config import MY_CLIENT_SECRET, MY_CLIENT_ID, MY_USERNAME, MY_PASSWORD
from utils.api_requests import APIClient

nexus_client = ApiClient('https://randers.nexus-review.kmd.dk:443/api/core/mobile/randers/v2/', client_id=MY_CLIENT_ID, client_secret=MY_CLIENT_SECRET)
sbsys_client = ApiClient('https://sbsip-web-test01.randers.dk:8543/', client_id=MY_CLIENT_ID, client_secret=MY_CLIENT_SECRET, username=MY_USERNAME, password=MY_PASSWORD)
```
* Certifikat, fx. delta
```
from utils.config import MY_BASE64_CERT, MY_PASSWORD
from utils.api_requests import APIClient

delta_client = ApiClient('https://randers.nexus-review.kmd.dk:443/api/core/mobile/randers/v2/', cert_base64=MY_BASE64_CERT, password=MY_PASSWORD)
```
* Requests
```
# GET requests
my_api_client.make_request(path='some/path')
my_api_client.make_request(method='get', path='some/path')

# POST requests
my_dict = {'key': 'value'}
my_api_client.make_request(path='some/path', json=my_dict)

my_json = json.dumps(my_dict)
my_api_client.make_request(method='POST', path='some/path', data=my_json)

# PUT or DELETE
my_api_client.make_request(method='PUT', path='some/path', json=my_dict)
my_api_client.make_request(method='delete', path='some/path', json=my_dict)
```

### SFTP - forbind til ftp server
SFTPClient kan håntere flere typer authentication, eksempel på brug herunder:
* Username og password
```
from utils.config import HOST, USERNAME, PASSWORD
from utils.sftp import SFTPClient

client = SFTPClient(HOST, USERNAME, PASSWORD)
```
* SSH nøgle
```
from utils.config import HOST, USERNAME, BASE64_SSH_KEY
from utils.sftp import SFTPClient

client = SFTPClient(HOST, USERNAME, key_base64=BASE64_SSH_KEY)
```
* kodeordsbeskyttet SSH nøgle
```
from utils.config import HOST, USERNAME, BASE64_SSH_KEY, SSH_KEY_PASS
from utils.sftp import SFTPClient

client = SFTPClient(HOST, USERNAME, key_base64=BASE64_SSH_KEY,  key_pass=SSH_KEY_PASS)
```
* Forbind og brug som [pysftp](https://pysftp.readthedocs.io/)
```
with client.get_connection() as conn:
    print(conn.listdir())
    my_file = conn.open('somepath/some_remote_file.txt')

```

### Skriv til filer
* Hvis der skal skrives til filer skal det være på et eksternt mount
* Eksempel til at test lokalt [docker-compose.yml](/docker-compose.yml#L18)

### Scheduler - kør kode på bestemt tidspunkt eller med interval
* Lav endpoint der starter jobbet og Kald endpoint med cronjob i kubenetes
