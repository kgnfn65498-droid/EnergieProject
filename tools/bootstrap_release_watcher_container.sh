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

mkdir -p "$INBOX/incoming" "$INBOX/logs"

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
  -e ENERGIE_ROOT=/energy \
  -e ENERGIE_WATCH_INTERVAL=5 \
  -e ENERGIE_ZIP_STABLE_POLLS=3 \
  -e ENERGIE_WATCHER_HEARTBEAT_STALE_SECONDS=30 \
  -v "$ROOT:/energy" \
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
