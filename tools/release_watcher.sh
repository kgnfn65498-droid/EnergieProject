#!/bin/sh
set -eu
if [ -n "${ENERGIE_ROOT:-}" ]; then ROOT="$ENERGIE_ROOT"; elif [ -d /energy/App ]; then ROOT=/energy; else echo "FOUT: ENERGIE_ROOT ontbreekt" >&2; exit 1; fi
exec python3 "$ROOT/App/tools/release_controller_service.py" --root "$ROOT" --interval "${ENERGIE_WATCH_INTERVAL:-5}" --stable-polls "${ENERGIE_ZIP_STABLE_POLLS:-3}" --ingress-stale-seconds "${ENERGIE_INGRESS_STALE_SECONDS:-600}"
