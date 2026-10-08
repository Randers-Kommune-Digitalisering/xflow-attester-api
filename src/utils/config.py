import os
from dotenv import load_dotenv


# loads .env file, will not override already set environment variables
# (will do nothing when testing, building and deploying)
load_dotenv()


DEBUG = os.getenv('DEBUG', 'False') in ['True', 'true']
PORT = os.getenv('PORT', '8080')
POD_NAME = os.getenv('POD_NAME', 'pod_name_not_set')

ATTEST_DB_TYPE = os.getenv('ATTEST_DB_TYPE', 'mssql').strip()
ATTEST_DB_HOST = os.getenv('ATTEST_DB_HOST', '').strip()
ATTEST_DB_NAME = os.getenv('ATTEST_DB_NAME', '').strip()
ATTEST_DB_USERNAME = os.getenv('ATTEST_DB_USERNAME', '').strip()
ATTEST_DB_PASSWORD = os.getenv('ATTEST_DB_PASSWORD', '').strip()
ATTEST_DB_PORT = os.getenv('ATTEST_DB_PORT', '').strip() or None

SFTP_HOST = os.getenv("SFTP_HOST", "")
SFTP_USERNAME = os.getenv("SFTP_USERNAME", "")
SFTP_PASSWORD = os.getenv("SFTP_PASSWORD")
SFTP_KEY_BASE64 = os.getenv("SFTP_KEY_BASE64")
SFTP_KEY_PASS = os.getenv("SFTP_KEY_PASS")
