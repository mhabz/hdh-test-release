"""Fixtures used by the tests: connect to the server, clean up files after."""

from __future__ import annotations

import logging
import shutil

import pytest

from infra_tests.settings import (
    PROJECT_ROOT,
    ExpectedFile,
    ServerConfig,
    get_expected_files,
    get_server,
    get_ssh_known_hosts_path,
    get_ssh_private_key_passphrase,
    get_ssh_private_key_path,
)
from infra_tests.ssh.client import SSHClient

logger = logging.getLogger(__name__)

DOWNLOADS_DIR = PROJECT_ROOT / "downloads"


@pytest.fixture
def server_config() -> ServerConfig:
    return get_server()


@pytest.fixture
def expected_files() -> list[ExpectedFile]:
    return get_expected_files()


@pytest.fixture
def downloads_dir():
    return DOWNLOADS_DIR


@pytest.fixture
def ssh_client(server_config: ServerConfig):
    """Connect to the server before the test runs, and close it after.

    If the connection fails, the test fails right away with a clear error,
    instead of failing later in a confusing way.
    """
    client = SSHClient(
        host=server_config.host,
        port=server_config.port,
        username=server_config.username,
        private_key_path=get_ssh_private_key_path(),
        private_key_passphrase=get_ssh_private_key_passphrase(),
        known_hosts_path=get_ssh_known_hosts_path(),
    )
    client.connect()
    yield client
    client.close()
    logger.info("Test finished, SSH connection closed")


@pytest.fixture(autouse=True)
def clean_downloads():
    """Delete any file downloaded during a test, once that test is done.

    This runs automatically for every test, even if the test failed.
    """
    yield
    if not DOWNLOADS_DIR.exists():
        return
    for item in DOWNLOADS_DIR.iterdir():
        if item.name == ".gitkeep":
            continue
        logger.info("Cleaning up downloaded file: %s", item)
        if item.is_file():
            item.unlink()
        else:
            shutil.rmtree(item)
