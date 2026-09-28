#!/bin/sh
# Resolve one Type2 system path. Falls back to historical Inbox only until a
# verified migration activation marker exists. After activation, canonical Data/03_Systeem is permanent.
energie_system_path(){
  ROOT="$1"; KEY="$2"; SOURCE="$3"; DEST="$4"
  MARKER="$ROOT/Data/03_Systeem/Projectmanager/ClearUp/PathActivation/$KEY.json"
  DEST_PATH="$ROOT/$DEST"
  ACTIVE=0
  if [ -f "$MARKER" ] && [ ! -L "$MARKER" ] && grep -Eq '"active"[[:space:]]*:[[:space:]]*true' "$MARKER" 2>/dev/null; then
    DEST_PARENT=$(dirname "$DEST_PATH")
    if [ -L "$DEST_PATH" ] || [ -L "$DEST_PARENT" ]; then
      echo "FOUT: canonical system path is symlink: $DEST_PATH" >&2
      return 2
    fi
    ACTIVE=1
  fi
  if [ "$ACTIVE" -eq 1 ]; then
    printf '%s\n' "$DEST_PATH"
  else
    printf '%s\n' "$ROOT/$SOURCE"
  fi
}
