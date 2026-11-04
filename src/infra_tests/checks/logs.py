"""Checks related to system log files (Test 1)."""

from __future__ import annotations

import logging
import shlex

from infra_tests.ssh.client import SSHClient

logger = logging.getLogger(__name__)


def check_log_file_exists(client: SSHClient, remote_path: str) -> bool:
    """Run a command on the server to check if a file exists.

    This test is about SSH command execution, not file transfer, so it
    runs a shell `test -e` on the server instead of asking SFTP.
    """
    logger.info("Checking that log file exists: %s", remote_path)
    command = f"test -e {shlex.quote(remote_path)}"
    exit_status, _, _ = client.run_command(command)
    exists = exit_status == 0
    logger.info("Log file %s: %s", remote_path, "found" if exists else "not found")
    return exists
