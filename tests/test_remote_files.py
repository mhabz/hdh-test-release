"""Test 3: check the existence and size of remote files."""

from infra_tests.checks.remote_files import check_remote_files


def test_expected_files_exist_with_correct_size(ssh_client, expected_files):
    results = check_remote_files(ssh_client, expected_files)
    failures = [result for result in results if not result.ok]
    assert not failures, "\n".join(
        f"- {result.path}: exists={result.exists}, "
        f"expected={result.expected_size_bytes}, actual={result.actual_size_bytes}"
        for result in failures
    )
