# Setup

## Prerequisites

- Python 3.10+ (any recent Python 3 works; adjust if the team standard differs).
- Network access from your machine (or the CI runner) to the target server's SSH port.
- An SSH key pair already deployed: the **public** key authorized on the target server
  (in its `~/.ssh/authorized_keys`), and the **private** key available locally.

## 1. Create a virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Configure secrets (never committed)

Copy the example environment file and fill in your real values:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
SSH_PRIVATE_KEY_PATH=~/.ssh/id_ed25519
SSH_PRIVATE_KEY_PASSPHRASE=
```

- `SSH_PRIVATE_KEY_PATH`: path to your private key. Leave the default if you already use
  `~/.ssh/id_ed25519`; otherwise point it to your own key.
- `SSH_PRIVATE_KEY_PASSPHRASE`: only needed if your key is passphrase-protected; leave
  empty otherwise.

`.env` is listed in `.gitignore` and must never be committed.

## 3. Set up the local Docker SSH target

The test suite's default target is a disposable Docker container (Ubuntu + `openssh-server`),
not a real server. This keeps testing self-contained and never touches your real SSH
configuration.

### 3.1 Generate a dedicated keypair

This key is only for the Docker fixture. Never reuse your personal/real SSH key here.

```bash
ssh-keygen -t ed25519 -f docker/ssh/id_ed25519 -N ""
```

This creates `docker/ssh/id_ed25519` (private) and `docker/ssh/id_ed25519.pub` (public).
Both are git-ignored. The public key is baked into the image at build time
(`docker/Dockerfile`); the private key is what you point `SSH_PRIVATE_KEY_PATH` to.

### 3.2 Build and start the container

```bash
docker compose up -d --build
```

This exposes the container's SSH server on `localhost:2222`.

### 3.3 Trust the container's host key

Strict host-key checking stays on, but it must not use your real `~/.ssh/known_hosts`.
Build a project-local one instead:

```bash
ssh-keyscan -p 2222 localhost > docker/known_hosts
```

Re-run this if you ever remove the `ssh_host_keys` Docker volume (that would generate a
new host key).

### 3.4 Point `.env` at the Docker target

```dotenv
SSH_PRIVATE_KEY_PATH=./docker/ssh/id_ed25519
SSH_PRIVATE_KEY_PASSPHRASE=
SSH_KNOWN_HOSTS_PATH=./docker/known_hosts
```

`config/servers.yaml` and `config/expected_files.yaml` already default to this container's
values (see below), so no further configuration is needed for a local run.

## 4. Configure the server inventory

`config/servers.yaml` already points at the local Docker target by default:

```yaml
servers:
  - name: main
    host: localhost
    port: 2222
    username: testuser
    auth_log_path: /var/log/auth.log
    cron_log_path: /var/log/cron.log
```

To target a real server instead, replace these values (and `/var/log/syslog` or
`/var/log/secure` may be the right `cron_log_path`/`auth_log_path` depending on the
distribution). No secret belongs in this file — only host, port, username, and log paths.

## 5. Configure the expected files (Test 3)

`config/expected_files.yaml` already matches the 5 fixture files the Docker container
creates on startup (`docker/entrypoint.sh`):

```yaml
expected_files:
  - path: /opt/fixtures/file1.bin
    expected_size_bytes: 1024
  # ... up to 5 entries
```

To target a real server, replace these with the real remote paths and their expected
exact size in bytes.

## 6. Run the tests

```bash
pytest
```

To generate both report formats:

```bash
pytest --html=reports/report.html --junitxml=reports/results.xml
```

- `reports/report.html` — human-readable report.
- `reports/results.xml` — JUnit XML, the standard format most CI systems consume
  natively for test reporting.

## 7. Running from a CI system

- Store the private key as a CI **secret/credential** and inject it into the job as
  `SSH_PRIVATE_KEY_PATH` (or a file the CI writes and you point the variable to) — no
  code change is required, only job/pipeline configuration.
- Most CI systems (GitLab CI, GitHub Actions, Jenkins, etc.) have a built-in way to
  publish `reports/results.xml` (JUnit XML) as test results in the build UI.
- Archive `reports/report.html` as a build artifact if a human-readable report is also
  wanted.

## Troubleshooting

- **Connection refused / timeout**: verify `host`/`port` in `config/servers.yaml` and
  that the server's firewall allows SSH from where the tests run.
- **Authentication failure**: verify `SSH_PRIVATE_KEY_PATH` points to a valid private
  key and that the matching public key is in the target user's `authorized_keys`.
- **Permission denied reading a log file**: the configured user may not have read
  access (e.g. `auth.log` is often restricted to `root`/`adm`). This is treated as an
  expected failure mode, not a bug — see
  [technical-decisions.md](technical-decisions.md#2-permissions-on-remote-files-no-assumption-of-sudo).
