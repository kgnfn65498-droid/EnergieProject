#!/bin/sh
# Resolve one Type2 system path. Falls back to the historical Inbox path until
# a verified migration activation marker exists and the destination is present.
energie_system_path(){
  ROOT="$1"; KEY="$2"; SOURCE="$3"; DEST="$4"
  MARKER="$ROOT/Data/03_Systeem/Projectmanager/ClearUp/PathActivation/$KEY.json"
  DEST_PATH="$ROOT/$DEST"
  ACTIVE=0
  if [ -f "$MARKER" ] && [ ! -L "$MARKER" ] && grep -Fq '"active": true' "$MARKER" 2>/dev/null; then
    if [ -e "$DEST_PATH" ] && [ ! -L "$DEST_PATH" ]; then
      ACTIVE=1
    else
      case "$KEY" in
        publisher_history|latest_release_status|watcher_contract|control_plane_yaml|watcher_heartbeat_legacy|watcher_heartbeat_v2|atomic_state|github_publication_state|github_publisher_state|nas_cr_lock|release_controller_lock|release_transition_lock)
          DEST_PARENT=$(dirname "$DEST_PATH")
          [ -d "$DEST_PARENT" ] && [ ! -L "$DEST_PARENT" ] && ACTIVE=1
          ;;
      esac
    fi
  fi
  if [ "$ACTIVE" -eq 1 ]; then
    printf '%s\n' "$DEST_PATH"
  else
    printf '%s\n' "$ROOT/$SOURCE"
  fi
}
