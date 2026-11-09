# Technical Decisions

This document lists the key technical choices made for `infra-tests`, with the reasoning
behind each one. Several open questions were resolved explicitly with the project owner;
those decisions are recorded here as the source of truth.

## 1. SSH authentication: private key only, no password

**Decision**: the SSH client only supports key-based authentication. There is no code
path for password authentication at all.

**Why**: the project's hard constraint is "no hardcoded secret or password". A private
key path is not a secret by itself (the key file is), and keeping password auth out of
the code entirely removes the temptation to hardcode one later. The key path (and an
optional passphrase) is read from environment variables (see `.env.example`).

## 2. Permissions on remote files: no assumption of `sudo`

**Decision**: none of the checks attempt to escalate privileges. If the configured user
cannot read a file over SFTP (Test 2's download, Test 3's stat), the check fails with an
explicit, actionable error (e.g. "permission denied reading `<path>` as `<user>` — check
file permissions or group membership"), rather than letting a raw Paramiko/SFTP
exception surface.

**Why**: `auth.log` and similar files are typically readable only by `root` or the `adm`
group on Debian/Ubuntu. Assuming `sudo` is available would make the test fragile and
would require granting elevated rights to the test account purely for testing purposes,
which is undesirable from a security standpoint.

**Note on Test 1**: since Test 1 runs a remote shell command (`test -e <path>`, see
decision 12) instead of going through SFTP, it only reports existence, not readability.
A missing file and a file hidden behind a permission issue both make `test -e` return a
non-zero exit status, so Test 1 cannot (and does not try to) tell them apart — that
distinction only matters for Tests 2 and 3, which actually read file content.

## 2b. Default test target: a local Docker container

**Decision**: the default target for running the suite locally is a disposable Docker
container (Ubuntu + `openssh-server`), built from `docker/Dockerfile` and started with
`docker-compose.yml`, instead of a real VPS or shared server.

**Why**: a container can be rebuilt from scratch at any time, so the suite always starts
from a known, reproducible state — no risk of testing against a server someone else is
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
`config/expected_files.yaml` — none of the checks or test code depend on the target being
a container.

## 2c. Host-key verification path is configurable

**Decision**: `SSHClient` accepts an optional `known_hosts_path`, read from a new
`SSH_KNOWN_HOSTS_PATH` environment variable (`settings.get_ssh_known_hosts_path`). When
unset, it falls back to the real `~/.ssh/known_hosts`, exactly as before.

**Why**: strict host-key checking (decision rejecting unknown hosts, see `SSHClient.connect`)
is kept in all cases — there is no code path that disables it. But testing against the
local Docker target means trusting a key that has nothing to do with the user's real SSH
setup, and this project must never read from or write to `~/.ssh` without being
explicitly told to. Making the path configurable lets the Docker target use its own,
project-local `docker/known_hosts` file (built with `ssh-keyscan`, see `docs/setup.md`)
while real-server usage keeps relying on the user's own `known_hosts`, unchanged.

## 2d. Dedicated keypair for the Docker fixture

**Decision**: the Docker target uses its own SSH keypair, generated locally into
`docker/ssh/` (git-ignored) and baked into the image as `authorized_keys`. It is never
the user's personal/real key, and it is never committed.

**Why**: the container is a disposable test fixture; giving it its own throwaway key
keeps it fully isolated from the user's real credentials, and means nothing sensitive is
at stake if the image or its build context were ever shared.

## 3. Log file paths are configurable, not hardcoded

**Decision**: `auth_log_path` and `cron_log_path` are read from `config/servers.yaml`
per server, not hardcoded in `checks/logs.py` or `checks/cron.py`.

**Why**: the exact path depends on the Linux distribution (`/var/log/auth.log` on
Debian/Ubuntu vs `/var/log/secure` on RHEL/CentOS for authentication logs; `/var/log/syslog`
vs `/var/log/cron` for CRON logs). Making the path part of the inventory means the same
code works across distributions without modification.

## 4. CRON check window: last 7 days (explicit assumption)

**Decision**: Test 2 checks that each of the last 7 days has at least one CRON
occurrence in the log, by default.

**Why**: the requirement ("at least one CRON occurrence per day") does not specify a
window. Seven days was chosen as a reasonable, explicit default that is long enough to
catch a stuck cron daemon, short enough to keep the check fast and the downloaded log
file small. This is a stated assumption, not a hidden one — it should be revisited if
the real need differs (e.g. by making it configurable).

## 5. File size comparison: strict equality by default

**Decision**: Test 3 compares the actual remote file size to the expected size in
`config/expected_files.yaml` with strict equality. No tolerance is applied unless
explicitly configured.

**Why**: an implicit tolerance would hide discrepancies that might matter (e.g. a
truncated file transfer). If a tolerance is ever needed, it should be an explicit,
visible field in the configuration (e.g. `tolerance_bytes`), not a hardcoded margin in
the code.

## 6. Server inventory as a list, from day one

**Decision**: `config/servers.yaml` stores servers as a list, even though only one
server is in scope today.

**Why**: starting with a list costs nothing now and avoids a breaking change to the
configuration format (and the code that reads it) the day a second server is added.

## 7. Configuration vs. secrets: strict separation

**Decision**:
- Non-sensitive data (host, port, username, log paths, expected file sizes) lives in
  versioned YAML files under `config/`.
- Secrets (the SSH private key, and its passphrase if any) are never stored in a
  versioned file. They are provided through environment variables, loaded via
  `python-dotenv` from a local, git-ignored `.env` file in development, or injected
  directly as environment variables/secrets by whatever CI system runs the suite in
  automated runs.

**Why**: this is an explicit project requirement ("no hardcoded secret or password").
It is also what makes the project genuinely portable across environments and safe to
version control in full.

## 8. Dependencies

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

## 9. Reporting: HTML and JUnit XML, both

**Decision**: every test run produces both an HTML report (`pytest-html`, for a human to
read) and a JUnit XML report (native pytest flag, for a CI system to parse).

**Why**: the two audiences are different. A human prefers a readable HTML page; most CI
systems (Jenkins, GitLab CI, GitHub Actions, ...) consume JUnit XML natively through
their built-in test-reporting features. Producing both costs one extra dependency and
one extra CLI flag.

## 10. Single requirements file

**Decision**: one `requirements.txt` for both runtime and development dependencies,
instead of splitting into `requirements.txt` / `requirements-dev.txt`.

**Why**: the split matters mainly when a package is deployed to production and should
not ship development tooling. This project is never installed as a package elsewhere —
it runs directly from its own repository, locally or in CI. A single file is simpler to
read, install, and present.

## 11. CI/CD target: no specific CI system required

**Decision**: the project is designed to run unmodified from any CI job (Jenkins,
GitLab CI, GitHub Actions, ...), without committing to one in particular — none is set
up for this project today.

**Why this works without extra code**:
- JUnit XML output is read natively by most CI systems' built-in test reporting.
- Secrets are expected as environment variables / a key file, which matches how every
  mainstream CI system's secret/credential mechanism injects values into a build — no
  code change needed, only job/pipeline configuration on whichever CI is chosen later.

## 12. Test 1 runs a remote shell command, not SFTP

**Decision**: `checks/logs.py` checks the log file's existence by running `test -e
<path>` on the server through `SSHClient.run_command` (which wraps Paramiko's
`exec_command`), and looking at the exit status — not by calling SFTP's `stat`.

**Why**: the brief for Test 1 explicitly asks for an SSH connection that "executes a
remote Linux command" to check the file, as a distinct skill from Tests 2 and 3, which
are about file transfer (SFTP download, SFTP stat). Keeping `run_command` as a separate,
general-purpose method on `SSHClient` also means any future check that needs to run an
arbitrary command on the server can reuse it.
