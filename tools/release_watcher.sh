#!/bin/sh
set -eu

if [ -n "${ENERGIE_ROOT:-}" ]; then
  ROOT="$ENERGIE_ROOT"
elif [ -d "/share/AI Projecten/EnergieProject/App" ]; then
  ROOT="/share/AI Projecten/EnergieProject"
elif [ -d "/share/Energie_NAS/EnergieProject/App" ]; then
  ROOT="/share/Energie_NAS/EnergieProject"
elif [ -d "/share/Energie_NAS/App" ]; then
  ROOT="/share/Energie_NAS"
else
  echo "FOUT: EnergieProject-root met App/Data/Backups/Inbox/Infra niet gevonden" >&2
  exit 1
fi
PROJECT="$ROOT/App"
INBOX="$ROOT/Inbox"
INCOMING="$INBOX/incoming"
PROCESSED="$INBOX/processed"
LOGDIR="$INBOX/logs"
INSTALLER_SOURCE="$PROJECT/tools/release_installer.sh"
PIDFILE="$INBOX/.watcher.pid"
WATCHER_LOCK="$INBOX/.watcher.lock"
STATUSFILE="$INBOX/latest_release_status.txt"
HEARTBEAT="$INBOX/.watcher.heartbeat"
ZIP_HELPER_SOURCE="$PROJECT/tools/release_zip.py"
CRASH_CLEANUP_REQUEST="$INBOX/crash_recovery_cleanup_request.json"
CRASH_CLEANUP_RESULT="$INBOX/crash_recovery_cleanup_result.json"
CRASH_CLEANUP_HELPER="$PROJECT/tools/crash_recovery_cleanup.py"
MODE_GATE="$PROJECT/tools/operating_mode_gate.py"
MCP_GUARD_HOTFIX_HELPER="$PROJECT/tools/mcp_system_path_guard_hotfix.py"
MCP_GUARD_HOTFIX_RESULT="$INBOX/logs/mcp_system_path_guard_hotfix_v3231.json"
HEARTBEAT_STALE_SECONDS="${ENERGIE_WATCHER_HEARTBEAT_STALE_SECONDS:-30}"
INTERVAL="${ENERGIE_WATCH_INTERVAL:-5}"
STABLE_POLLS="${ENERGIE_ZIP_STABLE_POLLS:-3}"
PROCESSED_RETENTION="${ENERGIE_PROCESSED_RETENTION:-3}"
LAST_ZIP=""
LAST_SIZE=""
LAST_MTIME=""
STABLE_COUNT=0

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
write_status(){
  STATUS=$1
  DETAIL=${2:-}
  TMP_STATUS="$STATUSFILE.tmp.$$"
  printf '%s | %s | %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$STATUS" "$DETAIL" > "$TMP_STATUS"
  mv "$TMP_STATUS" "$STATUSFILE"
}
mode_allows(){
  capability=$1
  [ -f "$MODE_GATE" ] || return 1
  command -v python3 >/dev/null 2>&1 || return 1
  python3 "$MODE_GATE" --root "$ROOT" --capability "$capability" >/dev/null 2>&1
}

zip_integrity_ok(){
  ZIP_PATH=$1
  if command -v python3 >/dev/null 2>&1 && [ -f "$ZIP_HELPER_SOURCE" ]; then
    python3 "$ZIP_HELPER_SOURCE" test "$ZIP_PATH" >/dev/null 2>&1
  else
    unzip -tqq "$ZIP_PATH" >/dev/null 2>&1
  fi
}

cleanup_processed_releases_on_start(){
  case "$PROCESSED_RETENTION" in
    ''|*[!0-9]*) PROCESSED_RETENTION=3 ;;
  esac
  [ "$PROCESSED_RETENTION" -ge 1 ] 2>/dev/null || PROCESSED_RETENTION=3
  mkdir -p "$PROCESSED"

  COUNT="$(find "$PROCESSED" -maxdepth 1 -type f -name 'EnergieProject_v*.zip' 2>/dev/null | wc -l | tr -d ' ')"
  log "Watcher startup-retentie v32.0.22: start count=$COUNT keep=$PROCESSED_RETENTION"
  [ "$COUNT" -gt "$PROCESSED_RETENTION" ] || {
    log "Watcher startup-retentie v32.0.22: niets op te ruimen"
    return 0
  }

  RANKED="$(mktemp /tmp/energie-processed-ranked.XXXXXX)" || return 1
  REMOVE="$(mktemp /tmp/energie-processed-remove.XXXXXX)" || {
    rm -f "$RANKED"
    return 1
  }

  for release_zip in "$PROCESSED"/EnergieProject_v*.zip; do
    [ -e "$release_zip" ] || continue
    base="$(basename "$release_zip")"
    version="${base#EnergieProject_v}"
    version="${version%.zip}"
    major="${version%%.*}"
    rest="${version#*.}"
    minor="${rest%%.*}"
    patch="${rest#*.}"
    case "$major:$minor:$patch" in
      *[!0-9:]*|'')
        log "WAARSCHUWING: processed ZIP met onbekende versie blijft behouden: $base"
        continue
        ;;
    esac
    printf '%09d.%09d.%09d %s\n' "$major" "$minor" "$patch" "$release_zip"
  done | sort -r > "$RANKED"

  tail -n +$((PROCESSED_RETENTION + 1)) "$RANKED" | cut -d' ' -f2- > "$REMOVE"

  while IFS= read -r old_release; do
    [ -n "$old_release" ] || continue
    if rm -f -- "$old_release"; then
      log "Watcher startup-retentie v32.0.22: verwijderd $(basename "$old_release")"
    else
      log "FOUT: watcher startup-retentie kon niet verwijderen: $(basename "$old_release")"
      rm -f "$RANKED" "$REMOVE"
      return 1
    fi
  done < "$REMOVE"

  rm -f "$RANKED" "$REMOVE"

  AFTER="$(find "$PROCESSED" -maxdepth 1 -type f -name 'EnergieProject_v*.zip' 2>/dev/null | wc -l | tr -d ' ')"
  if [ "$AFTER" -gt "$PROCESSED_RETENTION" ]; then
    log "FOUT: watcher startup-retentie eindcontrole count=$AFTER keep=$PROCESSED_RETENTION"
    return 1
  fi
  log "Watcher startup-retentie v32.0.22: OK count=$AFTER keep=$PROCESSED_RETENTION"
  return 0
}

heartbeat_age(){
  NOW="$(date +%s)"
  MODIFIED="$(date -r "$HEARTBEAT" +%s 2>/dev/null || echo 0)"
  [ "$MODIFIED" -gt 0 ] || { echo 999999; return; }
  echo $((NOW - MODIFIED))
}

touch_heartbeat(){
  printf '%s\n' "$(date +%s)" > "$HEARTBEAT.tmp.$$"
  mv "$HEARTBEAT.tmp.$$" "$HEARTBEAT"
}

process_mcp_guard_hotfix(){
  [ -f "$MCP_GUARD_HOTFIX_HELPER" ] || return 0
  if ! command -v python3 >/dev/null 2>&1; then
    log "FOUT: MCP system-path hotfix wacht; python3 ontbreekt in watchercontainer"
    return 1
  fi
  if python3 "$MCP_GUARD_HOTFIX_HELPER" --root "$ROOT" --result "$MCP_GUARD_HOTFIX_RESULT" >> "$LOGDIR/release_watcher.log" 2>&1; then
    log "MCP system-path guard hotfix toegepast/gecontroleerd; MCP-containerrestart vereist"
    return 0
  fi
  log "FOUT: MCP system-path guard hotfix niet volledig geslaagd; zie $MCP_GUARD_HOTFIX_RESULT"
  return 1
}

process_crash_recovery_cleanup(){
  [ -f "$CRASH_CLEANUP_REQUEST" ] || return 0
  if ! command -v python3 >/dev/null 2>&1; then
    log "FOUT: Crash Recovery cleanup wacht; python3 ontbreekt in watchercontainer"
    return 1
  fi
  if [ ! -f "$CRASH_CLEANUP_HELPER" ]; then
    log "FOUT: Crash Recovery cleanup helper ontbreekt: $CRASH_CLEANUP_HELPER"
    return 1
  fi

  if python3 "$CRASH_CLEANUP_HELPER" \
      --root "$ROOT" \
      --request "$CRASH_CLEANUP_REQUEST" \
      --result "$CRASH_CLEANUP_RESULT" >> "$LOGDIR/release_watcher.log" 2>&1; then
    log "Crash Recovery cleanup afgerond"
    rm -f "$CRASH_CLEANUP_REQUEST" 2>/dev/null || log "WAARSCHUWING: cleanup-request kon na verwerking niet worden verwijderd"
    return 0
  fi

  log "FOUT: Crash Recovery cleanup niet volledig geslaagd; resultaat blijft beschikbaar"
  [ -f "$CRASH_CLEANUP_RESULT" ] && rm -f "$CRASH_CLEANUP_REQUEST" 2>/dev/null || true
  return 1
}

run_installer(){
  [ -f "$INSTALLER_SOURCE" ] || { log "FOUT: installer ontbreekt: $INSTALLER_SOURCE"; return 1; }
  TMP_INSTALLER="/tmp/energie_release_installer.watcher.$$.sh"
  cp "$INSTALLER_SOURCE" "$TMP_INSTALLER" || { log "FOUT: installer kon niet naar /tmp worden gekopieerd"; return 1; }
  chmod 700 "$TMP_INSTALLER" || true
  if ENERGIE_INSTALLER_REEXEC=1 sh "$TMP_INSTALLER" >> "$LOGDIR/release_watcher.log" 2>&1; then
    rm -f "$TMP_INSTALLER"
    return 0
  else
    RC=$?
    rm -f "$TMP_INSTALLER"
    return "$RC"
  fi
}

case "${1:-run}" in
  status)
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "ACTIEF pid=$(cat "$PIDFILE")"; [ -f "$STATUSFILE" ] && cat "$STATUSFILE"; exit 0
    fi
    echo "NIET ACTIEF"; exit 1;;
  stop)
    if [ -f "$PIDFILE" ]; then kill "$(cat "$PIDFILE")" 2>/dev/null || true; rm -f "$PIDFILE"; fi
    rmdir "$WATCHER_LOCK" 2>/dev/null || true
    echo "GESTOPT"; exit 0;;
  once)
    run_installer; exit $?;;
  run) ;;
  *) echo "Gebruik: $0 [run|once|status|stop]" >&2; exit 2;;
esac

if ! mkdir "$WATCHER_LOCK" 2>/dev/null; then
  AGE="$(heartbeat_age)"
  if [ -f "$HEARTBEAT" ] && [ "$AGE" -lt "$HEARTBEAT_STALE_SECONDS" ]; then
    exit 0
  fi
  rm -f "$PIDFILE" "$HEARTBEAT" 2>/dev/null || true
  rmdir "$WATCHER_LOCK" 2>/dev/null || exit 0
  mkdir "$WATCHER_LOCK" 2>/dev/null || exit 0
fi

rm -f "$PIDFILE" 2>/dev/null || true
printf '%s\n' "$$" > "$PIDFILE"

cleanup_watcher(){
  rm -f "$PIDFILE" "$HEARTBEAT" 2>/dev/null || true
  rmdir "$WATCHER_LOCK" 2>/dev/null || true
}
refresh_watcher_from_installed_release(){
  NEW_WATCHER="$PROJECT/tools/release_watcher.sh"
  [ -f "$NEW_WATCHER" ] || return 1
  log "Watcher-refresh: autonoom overschakelen naar nieuw geïnstalleerde watcher"
  cleanup_watcher
  trap - EXIT INT TERM
  unset ENERGIE_WATCHER_REEXEC
  exec sh "$NEW_WATCHER" run
}
trap 'cleanup_watcher' EXIT INT TERM
touch_heartbeat
log "Release watcher gestart; interval=${INTERVAL}s"

if process_mcp_guard_hotfix; then
  log "MCP hotfix startupcontrole = OK"
else
  write_status "MAINTENANCE_FAILED" "mcp-system-path-hotfix; watcher blijft actief"
fi

if cleanup_processed_releases_on_start; then
  write_status "WATCHER_ACTIVE" "startup-retention-ok keep=${PROCESSED_RETENTION}"
else
  write_status "MAINTENANCE_FAILED" "processed-retention; watcher blijft actief"
fi
[ -f "$STATUSFILE" ] || write_status "WATCHER_ACTIVE" "interval=${INTERVAL}s"

while :; do
  touch_heartbeat

  if mode_allows maintenance_requests; then
    process_crash_recovery_cleanup || true
  fi

  if mode_allows release_ingress; then
    set -- "$INCOMING"/*.zip
    if [ -e "$1" ]; then
      COUNT=$#
      if [ "$COUNT" -eq 1 ]; then
        ZIP_PATH="$1"
        ZIP_NAME="$(basename "$ZIP_PATH")"
        ZIP_SIZE="$(wc -c < "$ZIP_PATH" 2>/dev/null | tr -d ' ' || echo 0)"
        ZIP_MTIME="$(date -r "$ZIP_PATH" +%s 2>/dev/null || echo 0)"

        if [ "$ZIP_NAME" = "$LAST_ZIP" ] && [ "$ZIP_SIZE" = "$LAST_SIZE" ] && [ "$ZIP_MTIME" = "$LAST_MTIME" ] && [ "$ZIP_SIZE" -gt 0 ]; then
          STABLE_COUNT=$((STABLE_COUNT + 1))
        else
          LAST_ZIP="$ZIP_NAME"
          LAST_SIZE="$ZIP_SIZE"
          LAST_MTIME="$ZIP_MTIME"
          STABLE_COUNT=1
          log "ZIP gedetecteerd; wacht op complete kopie: $ZIP_NAME (${ZIP_SIZE} bytes)"
          write_status "COPYING" "$ZIP_NAME"
        fi

        if [ "$STABLE_COUNT" -ge "$STABLE_POLLS" ]; then
          if zip_integrity_ok "$ZIP_PATH"; then
            log "ZIP stabiel en integraal na ${STABLE_COUNT} controles: $ZIP_NAME"
            write_status "PROCESSING" "$ZIP_NAME"
            if run_installer; then
              log "Automatische verwerking afgerond"
              write_status "SUCCESS" "$ZIP_NAME"
              refresh_watcher_from_installed_release
            else
              log "FOUT: automatische verwerking mislukt; zie installerlog en failed-map"
              write_status "FAILED" "$ZIP_NAME"
            fi
            LAST_ZIP=""
            LAST_SIZE=""
            LAST_MTIME=""
            STABLE_COUNT=0
          else
            log "ZIP nog niet compleet/integer; blijft in incoming: $ZIP_NAME"
            write_status "COPYING" "$ZIP_NAME"
            STABLE_COUNT=0
          fi
        fi
      else
        log "WACHT: $COUNT ZIP-bestanden in incoming; installer vereist exact één ZIP"
      fi
    fi
  fi
  sleep "$INTERVAL"
done
