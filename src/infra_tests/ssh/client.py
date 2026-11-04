"""Wrapper around Paramiko for the SSH/SFTP connection."""

from __future__ import annotations

import logging
from pathlib import Path

import paramiko

from infra_tests.exceptions import RemotePermissionError, SSHConnectionError

logger = logging.getLogger(__name__)


class SSHClient:
    """Wraps Paramiko so the rest of the project never calls it directly.

    If we ever need to change how we connect, we only change this file.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        private_key_path: Path,
        private_key_passphrase: str | None = None,
        timeout: int = 10,
        known_hosts_path: Path | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._private_key_path = private_key_path
        self._private_key_passphrase = private_key_passphrase
        self._timeout = timeout
        self._known_hosts_path = known_hosts_path
        self._client: paramiko.SSHClient | None = None
        self._sftp: paramiko.SFTPClient | None = None

    def connect(self) -> None:
        logger.info("Connecting to %s@%s:%s", self._username, self._host, self._port)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        client.load_system_host_keys(
            str(self._known_hosts_path) if self._known_hosts_path else None
        )
        try:
            client.connect(
                hostname=self._host,
                port=self._port,
                username=self._username,
                key_filename=str(self._private_key_path),
                passphrase=self._private_key_passphrase,
                timeout=self._timeout,
                allow_agent=False,
                look_for_keys=False,
            )
        except Exception as exc:
            raise SSHConnectionError(
                f"Could not connect to {self._username}@{self._host}:{self._port}: {exc}"
            ) from exc
        self._client = client
        self._sftp = client.open_sftp()
        logger.info("Connected to %s@%s:%s", self._username, self._host, self._port)

    def close(self) -> None:
        if self._sftp is not None:
            self._sftp.close()
            self._sftp = None
        if self._client is not None:
            self._client.close()
            self._client = None
        logger.info("Connection to %s@%s:%s closed", self._username, self._host, self._port)

    def __enter__(self) -> "SSHClient":
        self.connect()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def run_command(self, command: str) -> tuple[int, str, str]:
        """Run a shell command on the server and return its result.

        Gives back the exit status, what the command printed, and what it
        printed as an error, so the caller can decide what counts as success.
        """
        logger.info("Running command: %s", command)
        _, stdout, stderr = self._client.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        logger.info("Command exit status: %s", exit_status)
        return exit_status, out, err

    def stat(self, remote_path: str) -> paramiko.SFTPAttributes:
        logger.info("Checking remote file: %s", remote_path)
        try:
            return self._sftp.stat(remote_path)
        except PermissionError as exc:
            raise RemotePermissionError(
                f"Permission denied reading '{remote_path}' as '{self._username}'"
            ) from exc

    def download(self, remote_path: str, local_dir: Path) -> Path:
        local_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / Path(remote_path).name
        logger.info("Downloading %s to %s", remote_path, local_path)
        try:
            self._sftp.get(remote_path, str(local_path))
        except PermissionError as exc:
            raise RemotePermissionError(
                f"Permission denied reading '{remote_path}' as '{self._username}'"
            ) from exc
        return local_path
