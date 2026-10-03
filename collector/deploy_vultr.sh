#!/bin/bash
# Deploy the recorder to a fresh Ubuntu server from this Mac. Run from the repo root:
#   collector/deploy_vultr.sh <server-ip> [--tiger]
# The IP is only an argument; never write it into the repo.
# Needs: root SSH without a password, secrets/kalshi.env + secrets/kalshi.pem locally.
# What it does:
#   1. rsync code (no data/, out/, .venv, .env, secrets/, keys) to /opt/gqh
#   2. server .env = local .env with TIGER_DATABASE_URL blanked unless --tiger (only one recorder
#      should write the shared Tiger table, which has no machine column); values are never printed
#   3. Kalshi key -> /opt/gqh/secrets/kalshi.pem (600) and /opt/gqh/secrets/kalshi.env with the
#      server path (dir 700)
#   4. server outage log at /opt/gqh/out/GAPS_vultr.md (not synced, so a redeploy never overwrites it)
#   5. chrony (NTP), python venv + requirements, systemd unit, start; print status and first log lines
set -euo pipefail
IP="${1:?usage: collector/deploy_vultr.sh <server-ip> [--tiger]}"
TIGER="${2:-}"
cd "$(dirname "$0")/.."
DEST="root@$IP"
[ -f secrets/kalshi.env ] && [ -f secrets/kalshi.pem ] || { echo "missing secrets/kalshi.env or secrets/kalshi.pem"; exit 1; }

rsync -az --delete --exclude '.git' --exclude '.venv' --exclude 'data/' --exclude 'out/' --exclude '.claude/' \
  --exclude '.env' --exclude 'secrets/' --exclude '*.pem' --exclude '*.key' --exclude '__pycache__' ./ "$DEST:/opt/gqh/"

ssh "$DEST" 'mkdir -p /opt/gqh/secrets /opt/gqh/data /opt/gqh/out && chmod 700 /opt/gqh/secrets'
# The server keeps its own outage log outside the synced tree (rsync would overwrite the repo GAPS.md).
SERVER_ENV_EXTRA='COLLECTOR_GAPS_MD=/opt/gqh/out/GAPS_vultr.md'
if [ "$TIGER" = "--tiger" ]; then
  { grep -v '^COLLECTOR_GAPS_MD=' .env; echo "$SERVER_ENV_EXTRA"; } | ssh "$DEST" 'cat > /opt/gqh/.env && chmod 600 /opt/gqh/.env'
else
  { sed 's#^TIGER_DATABASE_URL=.*#TIGER_DATABASE_URL=#' .env | grep -v '^COLLECTOR_GAPS_MD='; echo "$SERVER_ENV_EXTRA"; } \
    | ssh "$DEST" 'cat > /opt/gqh/.env && chmod 600 /opt/gqh/.env'
fi
scp -q secrets/kalshi.pem "$DEST:/opt/gqh/secrets/kalshi.pem"
{ grep '^KALSHI_API_KEY_ID=' secrets/kalshi.env; echo 'KALSHI_PRIVATE_KEY_PATH=/opt/gqh/secrets/kalshi.pem'; } \
  | ssh "$DEST" 'cat > /opt/gqh/secrets/kalshi.env && chmod 600 /opt/gqh/secrets/kalshi.env /opt/gqh/secrets/kalshi.pem'

ssh "$DEST" bash -s <<'REMOTE'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq python3-venv python3-pip rsync chrony >/dev/null
systemctl enable --now chrony >/dev/null 2>&1 || systemctl enable --now chronyd >/dev/null 2>&1 || true
cd /opt/gqh
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip && .venv/bin/pip install -q -r requirements.txt
cp collector/gqh-collector.service /etc/systemd/system/gqh-collector.service
systemctl daemon-reload
systemctl enable --now gqh-collector
sleep 20
systemctl --no-pager status gqh-collector | head -6
journalctl -u gqh-collector --no-pager -n 8
REMOTE
echo "Deployed. Health on the server: ssh $DEST 'cd /opt/gqh && .venv/bin/python -m collector.health --minutes 10'"
