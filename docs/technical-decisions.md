# Technical Decisions

This document lists the key technical choices made for `infra-tests`, with the reasoning
behind each one. Several open questions were resolved explicitly with the project owner;
those decisions are recorded here as the source of truth.

## 1. SSH authentication: private key only, no password

**Decision**: the SSH client only supports key-based authentication. There is no code
path for password authentication at all.


## 2. Permissions on remote files: no assumption of `sudo`

**Decision**: No sudo is used: the SSH user must have the required permissions to access the files. If access is denied,
the test reports a clear error instead of escalating privileges.

## 2b. Default test target: a local Docker container

**Decision**: the default target for running the suite locally is a disposable Docker
container (Ubuntu + `openssh-server`), built from `docker/Dockerfile` and started with
`docker-compose.yml`, instead of a real VPS or shared server.

**Why**: a container can be rebuilt from scratch at any time, so the suite always starts
from a known, reproducible state, no risk of testing against a server someone else is
relying on, and no dependency on a VPS being provisioned before the project's core logic
(Tests 1-3, config, reporting) can even be exercised.

Since a fresh container has no real multi-day history, `docker/entrypoint.sh` seeds
deterministic fixture data on every startup instead of waiting for real time to pass:
7 dated CRON log lines (one per of the last 7 days, matching the `_DATE_PREFIX` format
`checks/cron.py` already expects) and 5 files of fixed, known sizes under
`/opt/fixtures/` (matching `config/expected_files.yaml`). The container's SSH host keys
are persisted in a named Docker volume (`ssh_host_keys` on `/etc/ssh`) so they survive a
restart, and the client does not see a "host key changed" rejection every time.

Switching to a real server later only means editing `config/servers.yaml` and
`config/expected_files.yaml`, none of the checks or test code depend on the target being
a container.

## 3. CRON check window: last 7 days (explicit assumption)

**Decision**: Test 2 checks that each of the last 7 days has at least one CRON
occurrence in the log, by default.

## 4. File size comparison: strict equality by default

**Decision**: Test 3 compares the actual remote file size to the expected size in
`config/expected_files.yaml` with strict equality. No tolerance is applied unless
explicitly configured.

## 5. Server inventory as a list, from day one

**Decision**: `config/servers.yaml` stores servers as a list, even though only one
server is in scope today.

## 6. Configuration vs. secrets: strict separation

**Decision**:
- Non-sensitive data (host, port, username, log paths, expected file sizes) lives in
  versioned YAML files under `config/`.
- Secrets (the SSH private key, and its passphrase if any) are never stored in a
  versioned file. They are provided through environment variables, loaded via
  `python-dotenv` from a local, git-ignored `.env` file in development.

## 7. Dependencies

| Package | Role |
|---|---|
| `pytest` | test runner |
| `paramiko` | SSH/SFTP client |
| `PyYAML` | reading `config/*.yaml` |
| `python-dotenv` | loading `.env` in local development |
| `pytest-html` | human-readable HTML test report |
| `ruff` | linting (dev) |

JUnit XML reporting does not require an extra dependency: it is built into pytest via
`--junitxml=reports/results.xml`.

## 8. Reporting: HTML and JUnit XML, both

**Decision**: The project supports two report formats: HTML (pytest-html) for human-readable results and JUnit XML 
(built into pytest) for CI reporting.

## 9. Parallel test execution: not enabled for now

**Decision**: tests run sequentially with plain `pytest`. `pytest-xdist` is not a
dependency.

**Why**: the suite has only 3 short tests. Starting worker processes would cost about as
much as it saves, and it would add a dependency and some fixture changes for no real
gain.

**To use if the suite grows to more tests** (or to several servers):

- Install `pytest-xdist` and run `pytest -n auto`. Each worker is a separate process
  with its own SSH connection, so nothing is shared between tests.
- Make the `downloads_dir` fixture return pytest's built-in `tmp_path` (a unique
  temporary directory per test). Today the autouse `clean_downloads` fixture empties the
  shared `downloads/` folder after every test, so a finishing test could delete a file
  that another test is still downloading or parsing. With `tmp_path`, each test has its
  own folder and `clean_downloads` is no longer needed.
- Switch `log_cli` off or use `log_file`, since live console logs from several workers
  get mixed together.
- Watch the server's `MaxSessions` / `MaxStartups` limits if many workers target the same
  host.

The real benefit would come from parametrizing the tests per server (the inventory in
`config/servers.yaml` is already a list), so each (test, server) pair runs in parallel.

## 10. SSH connection scope: one connection per test

**Decision**: the `ssh_client` fixture keeps the default `function` scope, so each test
opens its own SSH connection and closes it at teardown.

**Why**:

- **Isolation**: a test that leaves the connection in a bad state (for example a command
  that hangs) cannot affect the next one.
- **Fail-fast per test**: the connection is verified in the setup of every test, as
  described in the test lifecycle in [architecture.md](architecture.md).
- **Negligible cost**: opening an SSH/SFTP connection takes a fraction of a second, which
  does not matter for 3 tests.

**To use if the suite grows to more tests**: `scope="session"` opens one connection for the whole run.
This requires `server_config` to be `session`-scoped too, otherwise pytest raises a
`ScopeMismatch`. Under `pytest-xdist` a session fixture is created once **per worker**,
not once overall, so there would be one connection per worker. It pays off once there are
many more tests or the server has high latency, at the price of less isolation and a
less clear error if the shared connection drops mid-run.

## 11. Reporting several failures: one test for all expected files

**Decision**: Test 3 (`test_expected_files_exist_with_correct_size`) checks every expected
file inside a single test and reports all failing files in one assertion message, instead
of using one parametrized test per file.

**Known limitation**: the short summary line at the end of a pytest run
(`FAILED tests/... - AssertionError: ...`) only shows the **first line** of the assertion
message. When several files fail, the message has one line per file, so only the first
failing file appears in that summary line. The full message with every failing file is
still available in the `FAILURES` section of the pytest output, in
`reports/report.html`, and in the logs.

**Why this is acceptable**: one test means one SSH connection and one pass over the list,
and nothing is lost, only the short summary is truncated.

**To use if the suite grows to more tests or more expected files**:

- **Single-line message**: join the failures with `"; "` instead of `"\n"`, so every
  failing file shows up in the short summary line (it may still be truncated by the
  terminal width).
- **One parametrized test per file**: each expected file gets its own PASSED/FAILED line
  in the terminal and in the HTML/JUnit reports:

  ```python
  @pytest.mark.parametrize("expected_file", get_expected_files(), ids=lambda f: f.path)
  def test_expected_file_exists_with_correct_size(ssh_client, expected_file):
      (result,) = check_remote_files(ssh_client, [expected_file])
      assert result.ok, (
          f"{result.path}: exists={result.exists}, "
          f"expected={result.expected_size_bytes}, actual={result.actual_size_bytes}"
      )
  ```

  Things to take into account:
  - With the default `function`-scoped `ssh_client`, this opens **one SSH connection per
    file** (5 instead of 1). See section 10 for the `session`-scoped alternative.
  - `get_expected_files()` runs at import/collection time, so a missing or invalid
    `config/expected_files.yaml` fails during collection instead of inside a test, which
    is harder to read.
  - One test becomes N lines in the reports, which is either useful detail or noise
    depending on what the reader needs.
  - The same pattern applies to Test 2 (one test per day), but that would download the
    cron log once per day unless the download is shared between cases.


