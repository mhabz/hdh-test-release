# Architecture

## Purpose

`infra-tests` is an automated infrastructure testing project. It connects to one or more
remote Linux servers over SSH and verifies, through pytest, that:

1. a system log file exists (e.g. `/var/log/auth.log`),
2. that log contains at least one CRON execution trace per day, over a defined window,
3. a set of expected files exist on the server and have the expected size.

The design goals are: simplicity, maintainability, clear separation between configuration
and code, no hardcoded secrets, and a straightforward path to CI/CD integration (Jenkins).

## Layered design

The project is split into three layers, each with a single responsibility:

```
tests/              -> orchestration layer (pytest: fixtures, assertions, lifecycle)
src/infra_tests/
  checks/            -> business/domain layer (what "correct" means for each check)
  ssh/               -> transport layer (how to talk to a remote server)
  settings.py        -> configuration loading (what server, what paths, what secrets)
```

This mirrors a classic dependency direction: `tests/` depends on `checks/`, `checks/`
depends on `ssh/`, and nothing depends on pytest except `tests/`. This means the checks
could be reused outside of pytest (e.g. in a small CLI script) without modification.

## Folder and file reference

```
infra-tests/
├── requirements.txt
├── pyproject.toml
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
├── config/
│   ├── servers.yaml
│   └── expected_files.yaml
├── docker/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   └── ssh/            # generated locally, git-ignored (keypair for the fixture)
├── src/
│   └── infra_tests/
│       ├── __init__.py
│       ├── settings.py
│       ├── exceptions.py
│       ├── ssh/
│       │   ├── __init__.py
│       │   └── client.py
│       └── checks/
│           ├── __init__.py
│           ├── logs.py
│           ├── cron.py
│           └── remote_files.py
├── tests/
│   ├── conftest.py
│   ├── test_logs.py
│   ├── test_cron.py
│   └── test_remote_files.py
├── downloads/
├── reports/
└── docs/
    ├── architecture.md
    ├── technical-decisions.md
    └── setup.md
```

- **`requirements.txt`** — all project dependencies (runtime and development, kept in a
  single file on purpose: see [technical-decisions.md](technical-decisions.md)).
- **`.env.example`** — documents which environment variables are required (SSH key path,
  optional passphrase). Never contains real secrets; copied to a local, git-ignored `.env`.
- **`.gitignore`** — excludes virtual environments, `.env`, and runtime output
  (`downloads/`, `reports/`).
- **`config/servers.yaml`** — the server inventory: host, port, username, and the
  non-sensitive paths each check needs (log file locations). No credentials.
- **`config/expected_files.yaml`** — the list of files Test 3 must find on the server,
  with their expected exact size in bytes.
- **`docker/`** — a disposable local SSH target used as the default test environment: a
  `Dockerfile` (Ubuntu + `openssh-server`) and an `entrypoint.sh` that seeds the fixture
  data (log lines, expected files) on every startup. See
  [technical-decisions.md](technical-decisions.md).
- **`docker-compose.yml`** — builds and runs the `docker/` image, exposing its SSH server
  on `localhost:2222` and persisting its host keys in a named volume.
- **`pyproject.toml`** — `ruff` configuration (linting only, run manually).
- **`src/infra_tests/settings.py`** — loads `servers.yaml` / `expected_files.yaml` and
  resolves secrets exclusively from environment variables (never from a committed file).
- **`src/infra_tests/exceptions.py`** — project-specific exceptions (e.g. a clear
  "permission denied while reading log file" error, instead of a raw Paramiko traceback).
- **`src/infra_tests/ssh/client.py`** — a thin wrapper around Paramiko: opens an
  SSH/SFTP connection, exposes simple operations (run a remote shell command, stat a
  remote path, download a file), and closes the connection. Tests and checks depend on
  this wrapper, not directly on Paramiko — if the underlying library ever changes, only
  this file moves.
- **`src/infra_tests/checks/logs.py`** — the logic for Test 1: runs a shell command on
  the server (`test -e <path>`) to check whether the configured log file exists.
- **`src/infra_tests/checks/cron.py`** — the logic for Test 2: parsing the log content
  and verifying at least one CRON occurrence exists per day over the configured window.
- **`src/infra_tests/checks/remote_files.py`** — the logic for Test 3: for each expected
  file, verify it exists and that its real size matches the expected size exactly.
- **`tests/conftest.py`** — pytest fixtures: a session/test-scoped SSH connection fixture
  that fails fast if the connection cannot be established (setup), and a fixture that
  deletes any locally downloaded file after the test, whether it passed or failed
  (teardown — see "Test lifecycle" below).
- **`tests/test_*.py`** — the actual pytest test functions. Each one is a thin layer that
  calls into `checks/` and asserts on the result; it contains no SSH or parsing logic
  itself.
- **`downloads/`** — local, temporary storage for files fetched over SFTP during a test
  run. Emptied by the teardown fixture after each test.
- **`reports/`** — pytest-html and JUnit XML output, generated when running the suite.

## Test lifecycle

```
pytest session start
   └─ for each test:
        SETUP   -> ssh_client fixture: open SSH connection, fail immediately
                   if it cannot be established (connection is verified before
                   any test body runs)
        TEST    -> test function calls into checks/*, asserts on the result
        TEARDOWN -> executed even if the test failed:
                   - delete any file downloaded into downloads/
                   - close the SSH connection
```

Pytest fixtures implement this naturally: code before `yield` is setup, code after
`yield` is teardown, and teardown always runs — even when the test raises an assertion
error — because pytest treats the `yield` as a try/finally boundary.

## Data flow for each test

- **Test 1 (log existence)**: `test_logs.py` → `checks/logs.py` → `ssh/client.py`
  (runs `test -e <auth_log_path>` as a remote shell command over the SSH session) →
  assertion on the command's exit status.
- **Test 2 (CRON occurrences)**: `test_cron.py` → `checks/cron.py` → `ssh/client.py`
  (SFTP download of the configured `cron_log_path` into `downloads/`) → local parsing of
  the downloaded file → assertion that each day in the configured window has at least
  one CRON line.
- **Test 3 (remote files)**: `test_remote_files.py` → `checks/remote_files.py` →
  `ssh/client.py` (SFTP `stat` on each path from `expected_files.yaml`) → assertion that
  the file exists and its size matches exactly.

## Why this shape scales to CI/CD

- Configuration (`config/*.yaml`) and secrets (environment variables) are both external
  to the code, so running the same test suite against a different server, or from a
  Jenkins job, requires no code change — only different config/environment values.
- `reports/` is where both the human-readable (`pytest-html`) and machine-readable
  (JUnit XML) outputs land, which is what a CI system like Jenkins consumes directly.
