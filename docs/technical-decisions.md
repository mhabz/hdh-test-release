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


