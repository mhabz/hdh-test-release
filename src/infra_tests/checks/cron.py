"""Checks related to CRON occurrences in the logs (Test 2)."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from infra_tests.ssh.client import SSHClient

logger = logging.getLogger(__name__)

CRON_MARKER = "CRON"
_DATE_PREFIX = re.compile(r"^([A-Za-z]{3}\s+\d{1,2})")


def _parse_day(line: str, year: int) -> date | None:
    """Read the date at the start of a log line, like "Nov  3 06:25:01".

    The log line never includes a year, so we assume the year we're given.
    """
    match = _DATE_PREFIX.match(line)
    if not match:
        return None
    try:
        parsed = datetime.strptime(f"{match.group(1)} {year}", "%b %d %Y")
    except ValueError:
        return None
    return parsed.date()


def find_missing_cron_days(
    client: SSHClient,
    remote_path: str,
    local_dir: Path,
    days: int = 7,
    reference_date: date | None = None,
) -> list[date]:
    """Download the log file and list which days have no CRON entry.

    Looks at the last `days` days, counting back from today. An empty
    result means every day had at least one CRON line.
    """
    reference_date = reference_date or date.today()
    local_path = client.download(remote_path, local_dir)
    content = local_path.read_text(errors="replace")

    days_with_cron: set[date] = set()
    for line in content.splitlines():
        if CRON_MARKER not in line:
            continue
        day = _parse_day(line, reference_date.year)
        if day is not None:
            days_with_cron.add(day)

    expected_days = [reference_date - timedelta(days=offset) for offset in range(days)]
    missing_days = [day for day in expected_days if day not in days_with_cron]
    for day in expected_days:
        status = "missing" if day in missing_days else "found"
        logger.info("Day %s: CRON entry %s", day, status)
    return missing_days
