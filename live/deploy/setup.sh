#!/usr/bin/env bash
# Set up the live trial on a fresh Ubuntu 24.04 machine. Run as root:
#
#     bash setup.sh <domain>            # for example 203-0-113-7.sslip.io
#
# NOT RUN YET (see README.md in this folder). It installs Caddy, checks the public repository out to
# /opt/docs-drift, and runs the service as an unprivileged user under systemd.
# The Clocked key is NOT handled here: put it in /etc/docsdrift-live.env yourself (see README.md).
set -euo pipefail

DOMAIN="${1:?usage: setup.sh <domain>}"
REPO="https://github.com/vigohan95/docs-drift.git"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git python3 debian-keyring debian-archive-keyring apt-transport-https curl gnupg
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -qq
  apt-get install -y -qq caddy
fi

id docsdrift >/dev/null 2>&1 || useradd --system --home /var/lib/docsdrift-live --shell /usr/sbin/nologin docsdrift
install -d -o docsdrift -g docsdrift -m 750 /var/lib/docsdrift-live
if [ -d /opt/docs-drift/.git ]; then git -C /opt/docs-drift pull --ff-only; else git clone --depth 1 "$REPO" /opt/docs-drift; fi

# the environment file holds the key; create it empty and locked down if it is not there yet
if [ ! -f /etc/docsdrift-live.env ]; then
  install -m 600 -o root -g root /dev/null /etc/docsdrift-live.env
  echo "LIVE_DATA_DIR=/var/lib/docsdrift-live" >> /etc/docsdrift-live.env
  echo "LIVE_TRUST_PROXY=1" >> /etc/docsdrift-live.env
  echo "LIVE_ALLOWED_ORIGINS=https://vigohan95.github.io" >> /etc/docsdrift-live.env
  echo "LIVE_BUDGET=3500" >> /etc/docsdrift-live.env
fi

install -m 644 /opt/docs-drift/live/deploy/docsdrift-live.service /etc/systemd/system/docsdrift-live.service
sed "s/__DOMAIN__/${DOMAIN}/" /opt/docs-drift/live/deploy/Caddyfile > /etc/caddy/Caddyfile
systemctl daemon-reload
systemctl enable docsdrift-live caddy
systemctl restart caddy
if grep -q '^CLOCKED_API_KEY=' /etc/docsdrift-live.env; then
  systemctl restart docsdrift-live
  sleep 2
  curl -fsS http://127.0.0.1:8787/api/status && echo
else
  echo "Add CLOCKED_API_KEY=... to /etc/docsdrift-live.env (mode 600), then: systemctl restart docsdrift-live"
fi
