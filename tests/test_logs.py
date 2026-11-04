"""Test 1: check the existence of the system log file."""

from infra_tests.checks.logs import check_log_file_exists


def test_auth_log_exists(ssh_client, server_config):
    assert check_log_file_exists(ssh_client, server_config.auth_log_path), (
        f"Expected log file '{server_config.auth_log_path}' to exist on "
        f"'{server_config.host}', but it was not found."
    )
