"""Existence and size checks for remote files (Test 3)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from infra_tests.settings import ExpectedFile
from infra_tests.ssh.client import SSHClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileCheckResult:
    path: str
    exists: bool
    expected_size_bytes: int
    actual_size_bytes: int | None

    @property
    def ok(self) -> bool:
        return self.exists and self.actual_size_bytes == self.expected_size_bytes


def check_remote_file(client: SSHClient, expected: ExpectedFile) -> FileCheckResult:
    """Check one file: does it exist, and is its size correct?"""
    try:
        attributes = client.stat(expected.path)
    except FileNotFoundError:
        logger.info("File %s: not found", expected.path)
        return FileCheckResult(
            path=expected.path,
            exists=False,
            expected_size_bytes=expected.expected_size_bytes,
            actual_size_bytes=None,
        )
    result = FileCheckResult(
        path=expected.path,
        exists=True,
        expected_size_bytes=expected.expected_size_bytes,
        actual_size_bytes=attributes.st_size,
    )
    logger.info(
        "File %s: expected=%s actual=%s (%s)",
        expected.path,
        result.expected_size_bytes,
        result.actual_size_bytes,
        "ok" if result.ok else "mismatch",
    )
    return result


def check_remote_files(
    client: SSHClient, expected_files: list[ExpectedFile]
) -> list[FileCheckResult]:
    """Check every expected file and return all results, not just the failures.

    This way a test can show every problem at once, instead of stopping
    at the first one.
    """
    return [check_remote_file(client, expected) for expected in expected_files]
