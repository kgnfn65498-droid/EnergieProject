#!/bin/sh
set -eu

CONFIRMATION="${1:-}"
if [ -n "${ENERGIE_ROOT:-}" ]; then ROOT="$ENERGIE_ROOT";
elif [ -d "/share/AI Projecten/EnergieProject/App" ]; then ROOT="/share/AI Projecten/EnergieProject";
elif [ -d "/share/Energie_NAS/EnergieProject/App" ]; then ROOT="/share/Energie_NAS/EnergieProject";
else echo "FOUT: EnergieProject-root niet gevonden" >&2; exit 1; fi
REQUEST="$ROOT/Inbox/watcher_recreate_request.json"
MARKER="$ROOT/Inbox/watcher_container_contract.json"
BOOTSTRAP="$ROOT/App/tools/bootstrap_release_watcher_container.sh"
CONTRACT="$ROOT/App/tools/watcher_container_contract.py"
VERSION="$(tr -d '\r\n ' < "$ROOT/App/VERSIE.txt")"
[ "$VERSION" = "32.4.39" ] || { echo "FOUT: actieve release is niet 32.4.39" >&2; exit 2; }
[ "$CONFIRMATION" = "RECREATE WATCHER 32.4.39" ] || { echo "FOUT: bevestiging moet exact zijn: RECREATE WATCHER 32.4.39" >&2; exit 3; }
[ -f "$REQUEST" ] && [ ! -L "$REQUEST" ] || { echo "FOUT: watcher recreate request ontbreekt/onveilig" >&2; exit 4; }
[ -f "$BOOTSTRAP" ] && [ -f "$CONTRACT" ] || { echo "FOUT: vaste watcher helpers ontbreken" >&2; exit 5; }
grep -Fq '"schema": "energie_watcher_recreate_request_v1"' "$REQUEST" || { echo "FOUT: request schema" >&2; exit 6; }
grep -Fq '"operation": "recreate_exact_energie_release_watcher"' "$REQUEST" || { echo "FOUT: request operation" >&2; exit 7; }
grep -Fq '"release_version": "32.4.39"' "$REQUEST" || { echo "FOUT: request release" >&2; exit 8; }
grep -Fq '"container": "energie-release-watcher"' "$REQUEST" || { echo "FOUT: request container" >&2; exit 9; }
grep -Fq '"contract_version": 3' "$REQUEST" || { echo "FOUT: request contract" >&2; exit 10; }
grep -Fq '"confirmation_required": "RECREATE WATCHER 32.4.39"' "$REQUEST" || { echo "FOUT: request confirmation" >&2; exit 11; }
sh "$BOOTSTRAP"
N=0
while [ "$N" -lt 20 ]; do
  if [ -f "$MARKER" ] && grep -Fq '"ready": true' "$MARKER" && grep -Fq '"contract_version": 3' "$MARKER"; then
    rm -f "$REQUEST"
    echo WATCHER_RECREATE_32_4_39_GREEN
    exit 0
  fi
  sleep 1
  N=$((N+1))
done
echo "FOUT: watcher recreate uitgevoerd maar contract-readback niet GREEN" >&2
exit 12
