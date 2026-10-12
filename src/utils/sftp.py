"""
SFTP client used to download files from the authorization server.
"""
import base64
import io
import logging
import warnings

import paramiko
import pysftp


class SFTPClient:
    """
    Open SFTP connections using password and/or base64-encoded RSA key.

    :param host: SFTP host.
    :param username: SFTP user.
    :param host_key: Expected server host key as "<key-type> <base64>", e.g. from `ssh-keyscan`.
    :param password: Optional SFTP password.
    :param key_base64: Optional base64-encoded RSA private key.
    :param key_pass: Optional passphrase for the private key.
    """

    def __init__(
        self: "SFTPClient",
        host: str,
        username: str,
        host_key: str,
        password: str | None = None,
        key_base64: str | None = None,
        key_pass: str | None = None,
    ) -> None:
        self.host = host
        self.username = username
        self.password = password

        with warnings.catch_warnings():
            # The ~/.ssh/known_hosts warning is irrelevant; the pinned host key is set below.
            warnings.filterwarnings("ignore", ".*Failed to load HostKeys.*")
            cnopts = pysftp.CnOpts()

        cnopts.hostkeys = self._make_host_keys(host, host_key)

        self.cnopts = cnopts

        if key_base64:
            self.key = self._make_key(key_base64, key_pass)
        else:
            self.key = None

        self.logger = logging.getLogger(__name__)

    def get_connection(self: "SFTPClient") -> pysftp.Connection | None:
        """
        Open a connection to the SFTP server.

        :return: An open connection, or None if connecting failed.
        """
        try:
            return pysftp.Connection(host=self.host, username=self.username, password=self.password, private_key=self.key, cnopts=self.cnopts)
        except Exception as e:
            self.logger.error(e)
            return None

    @staticmethod
    def _make_host_keys(host: str, host_key: str) -> paramiko.HostKeys:
        entry = paramiko.hostkeys.HostKeyEntry.from_line(f"{host} {host_key.strip()}")
        if entry is None or entry.key is None:
            raise ValueError("SFTP_HOST_KEY must be set to '<key-type> <base64-key>' for the SFTP server.")

        host_keys = paramiko.HostKeys()
        host_keys.add(host, entry.key.get_name(), entry.key)
        return host_keys

    def _make_key(self: "SFTPClient", key_base64: str, key_pass: str | None = None) -> paramiko.RSAKey:
        decoded_key = base64.b64decode(key_base64).decode("utf-8")
        private_key_file = io.StringIO()
        private_key_file.write(decoded_key)
        private_key_file.seek(0)
        return paramiko.RSAKey.from_private_key(private_key_file, password=key_pass)
