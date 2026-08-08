#!/bin/sh
set -eu

SHARE="${ENERGIE_SHARE:-/share/Energie_NAS}"
PROJECT="$SHARE/EnergieProject"
INBOX="$SHARE/EnergieProject_Inbox"
INCOMING="$INBOX/incoming"
LOGDIR="$INBOX/logs"
INSTALLER_SOURCE="$PROJECT/tools/release_installer.sh"
PIDFILE="$INBOX/.watcher.pid"
INTERVAL="${ENERGIE_WATCH_INTERVAL:-30}"

# Keep the long-running watcher outside the worktree too. This prevents an update
# from deleting the script file from which the watcher is currently running.
if [ "${ENERGIE_WATCHER_REEXEC:-0}" != "1" ]; then
  case "$0" in
    "$PROJECT"/*)
      TMP_WATCHER="/tmp/energie_release_watcher.$$.sh"
      cp "$0" "$TMP_WATCHER" || { echo "FOUT: watcher kon zichzelf niet naar /tmp kopieren" >&2; exit 1; }
      chmod 700 "$TMP_WATCHER" || true
      export ENERGIE_WATCHER_REEXEC=1
      exec sh "$TMP_WATCHER" "$@"
      ;;
  esac
fi

mkdir -p "$INCOMING" "$LOGDIR"
log(){ printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOGDIR/release_watcher.log"; }

run_installer(){
  [ -f "$INSTALLER_SOURCE" ] || { log "FOUT: installer ontbreekt: $INSTALLER_SOURCE"; return 1; }
  TMP_INSTALLER="/tmp/energie_release_installer.watcher.$$.sh"
  cp "$INSTALLER_SOURCE" "$TMP_INSTALLER" || { log "FOUT: installer kon niet naar /tmp worden gekopieerd"; return 1; }
  chmod 700 "$TMP_INSTALLER" || true
  if ENERGIE_INSTALLER_REEXEC=1 sh "$TMP_INSTALLER" >> "$LOGDIR/release_watcher.log" 2>&1; then
    rm -f "$TMP_INSTALLER"
    return 0
  fi
  RC=$?
  rm -f "$TMP_INSTALLER"
  return "$RC"
}

case "${1:-run}" in
  status)
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "ACTIEF pid=$(cat "$PIDFILE")"; exit 0
    fi
    echo "NIET ACTIEF"; exit 1;;
  stop)
    if [ -f "$PIDFILE" ]; then kill "$(cat "$PIDFILE")" 2>/dev/null || true; rm -f "$PIDFILE"; fi
    echo "GESTOPT"; exit 0;;
  once)
    run_installer; exit $?;;
  run) ;;
  *) echo "Gebruik: $0 [run|once|status|stop]" >&2; exit 2;;
esac

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  log "Watcher is al actief pid=$(cat "$PIDFILE")"; exit 0
fi
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT INT TERM
log "Release watcher gestart; interval=${INTERVAL}s"

while :; do
  set -- "$INCOMING"/*.zip
  if [ -e "$1" ]; then
    COUNT=$#
    if [ "$COUNT" -eq 1 ]; then
      log "ZIP gedetecteerd: $(basename "$1")"
      if run_installer; then
        log "Automatische verwerking afgerond"
      else
        log "FOUT: automatische verwerking mislukt; zie installerlog en failed-map"
      fi
    else
      log "WACHT: $COUNT ZIP-bestanden in incoming; installer vereist exact één ZIP"
    fi
  fi
  sleep "$INTERVAL"
done
