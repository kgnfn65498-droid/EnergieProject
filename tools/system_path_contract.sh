#!/bin/sh
# Resolve one Type2 system path. Falls back to the historical Inbox path until
# a verified migration activation marker exists and the destination is present.
energie_system_path(){
  ROOT="$1"; KEY="$2"; SOURCE="$3"; DEST="$4"
  MARKER="$ROOT/Data/03_Systeem/Projectmanager/ClearUp/PathActivation/$KEY.json"
  if [ -f "$MARKER" ] && [ ! -L "$MARKER" ] && [ -e "$ROOT/$DEST" ] && grep -Fq '"active": true' "$MARKER" 2>/dev/null; then
    printf '%s\n' "$ROOT/$DEST"
  else
    printf '%s\n' "$ROOT/$SOURCE"
  fi
}
