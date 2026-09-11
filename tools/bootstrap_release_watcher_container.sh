#!/bin/sh
set -eu

if [ -d "/share/AI Projecten/EnergieProject/App" ]; then
  ROOT="/share/AI Projecten/EnergieProject"
elif [ -d "/share/Energie_NAS/EnergieProject/App" ]; then
  ROOT="/share/Energie_NAS/EnergieProject"
elif [ -d "/share/Energie_NAS/App" ]; then
  ROOT="/share/Energie_NAS"
else
  echo "FOUT: EnergieProject-root met App/Data/Backups/Inbox/Infra niet gevonden" >&2
  exit 1
fi

INBOX="$ROOT/Inbox"
CONTAINER_NAME="energie-release-watcher"
IMAGE="${ENERGIE_WATCHER_IMAGE:-python:3.12-slim}"

DOCKER="$(command -v docker 2>/dev/null || true)"
if [ -z "$DOCKER" ]; then
  for candidate in \
    "/share/CACHEDEV1_DATA/.qpkg/container-station/bin/docker" \
    "/share/Container/container-station-data/lib/docker/bin/docker"
  do
    if [ -x "$candidate" ]; then
      DOCKER="$candidate"
      break
    fi
  done
fi
[ -n "$DOCKER" ] || { echo "FOUT: Docker CLI van Container Station niet gevonden" >&2; exit 1; }

mkdir -p "$INBOX/incoming" "$INBOX/logs" "$INBOX/nas_container_cr_local"
CAPABILITY_MARKER="$INBOX/nas_container_cr_local/capability.json"
CONTRACT_MARKER="$INBOX/watcher_container_contract.json"
CONTRACT_HELPER="$ROOT/App/tools/watcher_container_contract.py"
[ -f "$CONTRACT_HELPER" ] || { echo "FOUT: watcher container-contract helper ontbreekt" >&2; exit 1; }
rm -f "$CAPABILITY_MARKER" "$CONTRACT_MARKER" 2>/dev/null || true

# Oude losse watcher stoppen indien het PID op de host nog leeft.
if [ -f "$INBOX/.watcher.pid" ]; then
  OLD_PID="$(cat "$INBOX/.watcher.pid" 2>/dev/null || true)"
  case "$OLD_PID" in
    ''|*[!0-9]*) ;;
    *) kill "$OLD_PID" 2>/dev/null || true ;;
  esac
fi
rm -f "$INBOX/.watcher.pid" "$INBOX/.watcher.heartbeat" 2>/dev/null || true
rmdir "$INBOX/.watcher.lock" 2>/dev/null || true

"$DOCKER" rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

"$DOCKER" run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  --network none \
  --cap-drop ALL \
  --cap-add DAC_OVERRIDE \
  --cap-add DAC_READ_SEARCH \
  --cap-add FOWNER \
  --security-opt no-new-privileges \
  -e ENERGIE_ROOT=/energy \
  -e ENERGIE_WATCH_INTERVAL=5 \
  -e ENERGIE_ZIP_STABLE_POLLS=3 \
  -e ENERGIE_WATCHER_HEARTBEAT_STALE_SECONDS=30 \
  -e ENERGIE_WATCHER_CONTAINER_CONTRACT=3 \
  -e ENERGIE_BACKUP_RETENTION=999 \
  -e ENERGIE_PROCESSED_RETENTION=999 \
  -v "$ROOT:/energy" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  "$IMAGE" \
  sh /energy/App/tools/release_watcher.sh >/dev/null

sleep 3
if "$DOCKER" ps --filter "name=^/${CONTAINER_NAME}$" --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"; then
  echo "OK: $CONTAINER_NAME draait met automatische herstart"
else
  echo "FOUT: $CONTAINER_NAME draait niet" >&2
  "$DOCKER" logs "$CONTAINER_NAME" 2>&1 | tail -n 30 >&2 || true
  exit 1
fi

CONTRACT_READY=0
N=0
while [ "$N" -lt 20 ]; do
  if [ -f "$CONTRACT_MARKER" ] && grep -q '"ready"[[:space:]]*:[[:space:]]*true' "$CONTRACT_MARKER" 2>/dev/null; then
    CONTRACT_READY=1
    break
  fi
  sleep 1
  N=$((N + 1))
done
if [ "$CONTRACT_READY" -ne 1 ]; then
  echo "FOUT: watcher container-contract werd niet GREEN na recreate" >&2
  "$DOCKER" logs "$CONTAINER_NAME" 2>&1 | tail -n 50 >&2 || true
  exit 1
fi
echo "OK: watcher container-contract v3 is GREEN"

CAPABILITY_READY=0
N=0
while [ "$N" -lt 20 ]; do
  if [ -f "$CAPABILITY_MARKER" ] && grep -q '"ready"[[:space:]]*:[[:space:]]*true' "$CAPABILITY_MARKER" 2>/dev/null; then
    CAPABILITY_READY=1
    break
  fi
  sleep 1
  N=$((N + 1))
done
if [ "$CAPABILITY_READY" -ne 1 ]; then
  echo "FOUT: NAS Container CR lokale capability werd niet GREEN na watcher-recreate" >&2
  "$DOCKER" logs "$CONTAINER_NAME" 2>&1 | tail -n 50 >&2 || true
  exit 1
fi
echo "OK: NAS Container CR lokale capability is GREEN"
