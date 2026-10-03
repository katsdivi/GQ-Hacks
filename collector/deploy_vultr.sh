#!/bin/bash
# Deploy the recorder to a fresh Ubuntu Vultr box from this Mac. Run from the repo root:
#   collector/deploy_vultr.sh <server-ip> [path-to-kalshi-private-key.pem]
# Needs: ssh access as root (ssh-copy-id root@<ip> first), .env filled in locally.
# What it does:
#   1. rsync code (no data/, out/, .venv, .env) to /opt/gqh
#   2. copy .env (rewriting KALSHI_PRIVATE_KEY_PATH to /opt/gqh/keys/kalshi.pem) and the key, mode 600
#   3. install python venv + requirements, install and start the systemd unit
#   4. print service status and the first log lines
set -euo pipefail
IP="${1:?usage: collector/deploy_vultr.sh <server-ip> [kalshi-key.pem]}"
KEY="${2:-}"
cd "$(dirname "$0")/.."
DEST="root@$IP"

rsync -az --delete --exclude '.git' --exclude '.venv' --exclude 'data/' --exclude 'out/' \
  --exclude '.env' --exclude '*.pem' --exclude '__pycache__' ./ "$DEST:/opt/gqh/"

ssh "$DEST" 'mkdir -p /opt/gqh/keys /opt/gqh/data /opt/gqh/out && chmod 700 /opt/gqh/keys'
# .env goes over as a file; values are never printed.
sed 's#^KALSHI_PRIVATE_KEY_PATH=.*#KALSHI_PRIVATE_KEY_PATH=/opt/gqh/keys/kalshi.pem#' .env | ssh "$DEST" 'cat > /opt/gqh/.env && chmod 600 /opt/gqh/.env'
if [ -n "$KEY" ]; then scp -q "$KEY" "$DEST:/opt/gqh/keys/kalshi.pem" && ssh "$DEST" 'chmod 600 /opt/gqh/keys/kalshi.pem'; fi

ssh "$DEST" bash -s <<'REMOTE'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq python3-venv python3-pip rsync >/dev/null
timedatectl set-ntp true || true
cd /opt/gqh
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip && .venv/bin/pip install -q -r requirements.txt
cp collector/gqh-collector.service /etc/systemd/system/gqh-collector.service
systemctl daemon-reload
systemctl enable --now gqh-collector
sleep 15
systemctl --no-pager status gqh-collector | head -8
journalctl -u gqh-collector --no-pager -n 10
REMOTE
echo "Deployed. Restart test on the server:"
echo "  ssh $DEST 'cd /opt/gqh && .venv/bin/python -m collector.health --minutes 30; systemctl restart gqh-collector'"
