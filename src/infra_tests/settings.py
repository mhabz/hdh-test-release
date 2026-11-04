"""Loading of configuration (YAML) and secrets (environment variables)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

from infra_tests.exceptions import ConfigurationError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"

load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class ServerConfig:
    name: str
    host: str
    port: int
    username: str
    auth_log_path: str
    cron_log_path: str


@dataclass(frozen=True)
class ExpectedFile:
    path: str
    expected_size_bytes: int


def _load_yaml(filename: str) -> dict:
    path = CONFIG_DIR / filename
    if not path.is_file():
        raise ConfigurationError(f"Configuration file not found: {path}")
    with path.open("r") as stream:
        return yaml.safe_load(stream)


def get_server(name: str = "main") -> ServerConfig:
    servers = _load_yaml("servers.yaml")["servers"]
    for entry in servers:
        if entry["name"] == name:
            return ServerConfig(**entry)
    raise ConfigurationError(f"No server named '{name}' in servers.yaml")


def get_expected_files() -> list[ExpectedFile]:
    entries = _load_yaml("expected_files.yaml")["expected_files"]
    return [ExpectedFile(**entry) for entry in entries]


def get_ssh_private_key_path() -> Path:
    raw = os.environ.get("SSH_PRIVATE_KEY_PATH")
    if not raw:
        raise ConfigurationError("SSH_PRIVATE_KEY_PATH environment variable is not set")
    return Path(raw).expanduser()


def get_ssh_private_key_passphrase() -> str | None:
    return os.environ.get("SSH_PRIVATE_KEY_PASSPHRASE") or None


def get_ssh_known_hosts_path() -> Path:
    """Return the file used to check the server's identity.

    Defaults to the real `~/.ssh/known_hosts`. Can be pointed elsewhere
    (e.g. a project-local file for a local Docker target) so testing
    never has to touch your real SSH configuration.
    """
    raw = os.environ.get("SSH_KNOWN_HOSTS_PATH")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".ssh" / "known_hosts"
