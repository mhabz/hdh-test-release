#!/bin/bash
# Prepares the container's test data, then starts the SSH server.
# This runs every time the container starts, so the data is always fresh.
set -euo pipefail

mkdir -p /var/run/sshd

# Create the server's host keys if they are not already there (the
# /etc/ssh volume keeps them stable across restarts, so the client does
# not see the host key change every time).
ssh-keygen -A

# Make sure the auth log exists, like on a real server.
touch /var/log/auth.log
chmod 640 /var/log/auth.log

# Write one CRON line per day for the last 7 days, so Test 2 has
# something real to read without waiting a full week for actual cron runs.
CRON_LOG=/var/log/cron.log
: > "$CRON_LOG"
for offset in 6 5 4 3 2 1 0; do
    day=$(date -d "-${offset} day" "+%b %e %H:%M:%S")
    echo "${day} docker-ssh-target CRON[1000]: (testuser) CMD (echo hello)" >> "$CRON_LOG"
done

# Create the 5 files Test 3 expects, each with a known, fixed size.
mkdir -p /opt/fixtures
head -c 1024 /dev/urandom > /opt/fixtures/file1.bin
head -c 2048 /dev/urandom > /opt/fixtures/file2.bin
head -c 4096 /dev/urandom > /opt/fixtures/file3.bin
head -c 512  /dev/urandom > /opt/fixtures/file4.bin
head -c 8192 /dev/urandom > /opt/fixtures/file5.bin

exec /usr/sbin/sshd -D -e
