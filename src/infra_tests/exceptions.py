"""Exceptions specific to the infra-tests project."""


class ConfigurationError(Exception):
    """Raised when configuration or secrets cannot be loaded or are invalid."""


class SSHConnectionError(Exception):
    """Raised when an SSH connection cannot be established."""


class RemotePermissionError(Exception):
    """Raised when a remote path cannot be read due to insufficient permissions."""
