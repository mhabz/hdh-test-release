"""Test 2: check CRON occurrences in the logs."""

from infra_tests.checks.cron import find_missing_cron_days


def test_cron_runs_every_day(ssh_client, server_config, downloads_dir):
    missing_days = find_missing_cron_days(
        ssh_client, server_config.cron_log_path, downloads_dir
    )
    assert missing_days == [], (
        f"No CRON occurrence found for the following day(s): {missing_days}"
    )
