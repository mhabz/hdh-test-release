# infra-tests

Automated infrastructure testing project, based on **pytest** and **Paramiko** (SSH/SFTP).

It connects to a Linux server over SSH and checks:
- **Test 1** — a system log file exists (`/var/log/auth.log`), checked by running a
  remote shell command over the SSH session.
- **Test 2** — that log contains at least one CRON execution trace per day, over a
  defined window.
- **Test 3** — a set of expected files exist on the server and have the exact expected
  size.

No hardcoded secrets anywhere: credentials are either a local, git-ignored `.env` file
or CI credentials injected as environment variables. See
[docs/technical-decisions.md](docs/technical-decisions.md) for the full reasoning.

## Requirements

- Python 3.10+
- Docker (to run the default local test target — a disposable container, not a real
  server; see [docs/setup.md](docs/setup.md))

## Quick start

```bash
# 1. Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Start the local SSH test target
ssh-keygen -t ed25519 -f docker/ssh/id_ed25519 -N ""
docker compose up -d --build
ssh-keyscan -p 2222 localhost > docker/known_hosts

# 3. Configure secrets
cp .env.example .env
# edit .env: point SSH_PRIVATE_KEY_PATH and SSH_KNOWN_HOSTS_PATH to the files above

# 4. Run the tests
pytest --html=reports/report.html --junitxml=reports/results.xml
```

`config/servers.yaml` and `config/expected_files.yaml` already default to this local
Docker target — no further configuration needed for a local run. Full walkthrough,
troubleshooting, and how to target a real server instead: [docs/setup.md](docs/setup.md).

## Project layout

```
src/infra_tests/
  checks/      -> what "correct" means for each test (pure functions)
  ssh/         -> thin wrapper around Paramiko
  settings.py  -> loads config/*.yaml, resolves secrets from the environment
tests/         -> pytest fixtures and test functions
docker/        -> Dockerfile + entrypoint for the local SSH test target
config/        -> server inventory and expected files (no secrets)
```

Full breakdown: [docs/architecture.md](docs/architecture.md).

## Documentation

- [docs/architecture.md](docs/architecture.md) — project architecture and role of each component.
- [docs/technical-decisions.md](docs/technical-decisions.md) — technical choices and justifications.
- [docs/setup.md](docs/setup.md) — environment installation and configuration.
