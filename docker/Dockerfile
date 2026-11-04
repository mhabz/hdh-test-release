# Minimal Ubuntu container running an SSH server, used as a local target
# for the test suite. This is a disposable fixture, not a production image.

FROM ubuntu:22.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends openssh-server && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /var/run/sshd

ARG SSH_USER=testuser
ENV SSH_USER=${SSH_USER}

RUN useradd --create-home --shell /bin/bash "${SSH_USER}"

RUN mkdir -p /home/${SSH_USER}/.ssh && \
    chmod 700 /home/${SSH_USER}/.ssh && \
    chown -R ${SSH_USER}:${SSH_USER} /home/${SSH_USER}/.ssh

# The public key is generated locally (see docs/setup.md) and never committed.
COPY ssh/id_ed25519.pub /home/${SSH_USER}/.ssh/authorized_keys
RUN chmod 600 /home/${SSH_USER}/.ssh/authorized_keys && \
    chown ${SSH_USER}:${SSH_USER} /home/${SSH_USER}/.ssh/authorized_keys

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22
ENTRYPOINT ["/entrypoint.sh"]
