#!/usr/bin/with-contenv bashio
set -e
echo "[SlimmeMeterPortal] launcher gestart"
echo "[SlimmeMeterPortal] Python: $(python3 --version 2>&1)"
exec python3 -u /app/main.py
