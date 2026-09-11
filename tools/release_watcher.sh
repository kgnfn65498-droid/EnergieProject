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
ATOMIC_SWAP_LOCK="$INBOX/.atomic_app_swap.lock"
ATOMIC_SWAP_JOURNAL="$INBOX/atomic_app_swap_state.json"
STATUSFILE="$INBOX/latest_release_status.txt"
HEARTBEAT="$INBOX/.watcher.heartbeat"
HEARTBEAT_V2="$INBOX/watcher_heartbeat.v2"
ZIP_HELPER_SOURCE="$PROJECT/tools/release_zip.py"
CRASH_CLEANUP_REQUEST="$INBOX/crash_recovery_cleanup_request.json"
CRASH_CLEANUP_RESULT="$INBOX/crash_recovery_cleanup_result.json"
CRASH_CLEANUP_HELPER="$PROJECT/tools/crash_recovery_cleanup.py"
PROJECT_CLEARUP_REQUEST="$INBOX/project_clearup_move_request.json"
PROJECT_CLEARUP_RESULT="$INBOX/logs/project_clearup_move_result.json"
PROJECT_CLEARUP_EXECUTOR="$PROJECT/tools/project_clearup_move_executor.py"
MODE_GATE="$PROJECT/tools/operating_mode_gate.py"
MCP_GUARD_HOTFIX_HELPER="$PROJECT/tools/mcp_system_path_guard_hotfix.py"
CLEARUP_PREPARE="$PROJECT/tools/prepare_clearup_root.sh"
MCP_GUARD_HOTFIX_RESULT="$INBOX/logs/mcp_system_path_guard_hotfix_v3231.json"
CR_STANDARD_HOTFIX_HELPER="$PROJECT/tools/cr_standard_native_mcp_hotfix.py"
CR_STANDARD_HOTFIX_RESULT="$INBOX/logs/cr_standard_native_mcp_hotfix_v32438.json"
NAS_CR_LOCAL_DIR="$INBOX/nas_container_cr_local"
NAS_CR_LOCAL_REQUEST="$NAS_CR_LOCAL_DIR/request.json"
NAS_CR_LOCAL_RESULT="$NAS_CR_LOCAL_DIR/result.json"
NAS_CR_LOCAL_CAPABILITY="$NAS_CR_LOCAL_DIR/capability.json"
NAS_CR_LOCAL_EXECUTOR="$PROJECT/tools/nas_cr_local_executor.py"
NAS_CR_LOCAL_PROBE="$PROJECT/tools/nas_cr_local_probe.py"
NAS_CR_LOCAL_TIMEOUT="${ENERGIE_NAS_CR_LOCAL_TIMEOUT_SECONDS:-1200}"
PROJECT_CR_LOCAL_DIR="$INBOX/project_cr_local"
PROJECT_CR_LOCAL_REQUEST="$PROJECT_CR_LOCAL_DIR/request.json"
PROJECT_CR_LOCAL_RESULT="$PROJECT_CR_LOCAL_DIR/result.json"
PROJECT_CR_LOCAL_EXECUTOR="$PROJECT/tools/project_cr_local_executor.py"
PROJECT_CR_LOCAL_TIMEOUT="${ENERGIE_PROJECT_CR_LOCAL_TIMEOUT_SECONDS:-1200}"
WATCHER_CONTRACT_HELPER="$PROJECT/tools/watcher_container_contract.py"
WATCHER_CONTRACT_MARKER="$INBOX/watcher_container_contract.json"
NATIVE_MCP_GUARD="$PROJECT/tools/native_mcp_runtime_guard.py"
NATIVE_MCP_RUNTIME_CONTRACT_HOTFIX="$PROJECT/tools/native_mcp_runtime_contract_hotfix.py"
NATIVE_MCP_RELOAD_EXECUTOR="$PROJECT/tools/native_mcp_reload_executor.py"
NATIVE_MCP_RELOAD_REQUEST="$INBOX/native_mcp_runtime/reload_request.json"
NATIVE_MCP_RELOAD_RESULT="$INBOX/native_mcp_runtime/reload_result.json"
POST_RELEASE_MODE_HELPER="$PROJECT/tools/post_release_mode_transition.py"
CANONICAL_ROADMAP_MIGRATION="$PROJECT/slimmemeterportal_import/rootfs/app/projectmanager_v2/canonical_roadmap_migration.py"
CANONICAL_ROADMAP="$ROOT/Data/03_Systeem/Projectmanager/Roadmap/canonical_roadmap_v3.json"
CANONICAL_ROADMAP_MIGRATION_STATE="$INBOX/logs/canonical_roadmap_migration_32.4.39.json"
HEARTBEAT_STALE_SECONDS="${ENERGIE_WATCHER_HEARTBEAT_STALE_SECONDS:-30}"
MODE_GATE_TIMEOUT="${ENERGIE_MODE_GATE_TIMEOUT_SECONDS:-5}"
MAINTENANCE_HELPER_TIMEOUT="${ENERGIE_MAINTENANCE_HELPER_TIMEOUT_SECONDS:-20}"
PROJECT_CLEARUP_HELPER_TIMEOUT="${ENERGIE_CLEARUP_MOVE_HELPER_TIMEOUT_SECONDS:-900}"
BOUNDED_TERM_GRACE_SECONDS="${ENERGIE_BOUNDED_TERM_GRACE_SECONDS:-1}"
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
run_bounded(){
  timeout_seconds=$1
  shift
  "$@" &
  command_pid=$!
  (
    sleep "$timeout_seconds"
    if kill -0 "$command_pid" 2>/dev/null; then
      kill -TERM "$command_pid" 2>/dev/null || true
      sleep "$BOUNDED_TERM_GRACE_SECONDS"
      kill -KILL "$command_pid" 2>/dev/null || true
    fi
  ) &
  timer_pid=$!
  rc=0
  wait "$command_pid" || rc=$?
  kill "$timer_pid" 2>/dev/null || true
  wait "$timer_pid" 2>/dev/null || true
  return "$rc"
}

mode_allows(){
  capability=$1
  [ -f "$MODE_GATE" ] || return 1
  command -v python3 >/dev/null 2>&1 || return 1
  rc=0
  run_bounded "$MODE_GATE_TIMEOUT" python3 "$MODE_GATE" --root "$ROOT" --capability "$capability" >/dev/null 2>&1 || rc=$?
  [ "$rc" -eq 0 ] && return 0
  [ "$rc" -eq 3 ] && return 1
  log "WAARSCHUWING: operating-mode gate timeout/fout capability=$capability rc=$rc; fail-closed"
  return 1
}

atomic_swap_allows_release_ingress(){
  [ ! -d "$ATOMIC_SWAP_LOCK" ] || return 1
  [ -f "$ATOMIC_SWAP_JOURNAL" ] || return 0
  STATE="$(sed -n 's/.*"state"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$ATOMIC_SWAP_JOURNAL" 2>/dev/null | head -n 1)"
  case "$STATE" in
    ACCEPTED|ROLLED_BACK) return 0 ;;
    PREPARED|OLD_RENAMED|NEW_ACTIVE|LIVE_ACCEPTANCE) return 1 ;;
    *) return 1 ;;
  esac
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
  NOW_HEARTBEAT="$(date +%s)"
  # Keep inode identity stable for NAS/SMB observers: overwrite in place rather
  # than rename a new inode over the watched path. The v2 marker is the
  # canonical heartbeat for 32.4.20+ readers; legacy remains for compatibility.
  printf '%s\n' "$NOW_HEARTBEAT" > "$HEARTBEAT"
  printf '%s\n' "$NOW_HEARTBEAT" > "$HEARTBEAT_V2"
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

process_cr_standard_hotfix(){
  [ -f "$CR_STANDARD_HOTFIX_HELPER" ] || return 0
  if ! command -v python3 >/dev/null 2>&1; then
    log "FOUT: CR-standaardhotfix wacht; python3 ontbreekt in watchercontainer"
    return 1
  fi
  if python3 "$CR_STANDARD_HOTFIX_HELPER" --root "$ROOT" >> "$LOGDIR/release_watcher.log" 2>&1; then
    if [ -f "$CR_STANDARD_HOTFIX_RESULT" ] && grep -q '"mcp_restart_required"[[:space:]]*:[[:space:]]*true' "$CR_STANDARD_HOTFIX_RESULT" 2>/dev/null; then
      log "CR-standaardhotfix GREEN; bronwijziging native MCP vereist later expliciete procesreload voor live acceptance"
    else
      log "CR-standaardhotfix GREEN/idempotent"
    fi
    return 0
  fi
  log "FOUT: CR-standaardhotfix RED; NAS Container CR blijft fail-closed"
  return 1
}

process_watcher_container_contract(){
  [ -f "$WATCHER_CONTRACT_HELPER" ] || { log "FOUT: watcher contract helper ontbreekt"; return 1; }
  command -v python3 >/dev/null 2>&1 || return 1
  rc=0
  python3 "$WATCHER_CONTRACT_HELPER" --root "$ROOT" --request-recreate >> "$LOGDIR/release_watcher.log" 2>&1 || rc=$?
  [ "$rc" -eq 0 ] && { log "Watcher container-contract = GREEN"; return 0; }
  [ "$rc" -eq 3 ] && { log "Watcher container-contract = RECREATE_REQUIRED"; return 1; }
  log "FOUT: watcher container-contract probe rc=$rc"
  return 1
}

process_native_mcp_runtime_contract_hotfix(){
  [ -f "$NATIVE_MCP_RUNTIME_CONTRACT_HOTFIX" ] || { log "FOUT: native MCP runtime-contract hotfix ontbreekt"; return 1; }
  command -v python3 >/dev/null 2>&1 || return 1
  if python3 "$NATIVE_MCP_RUNTIME_CONTRACT_HOTFIX" --root "$ROOT" >> "$LOGDIR/release_watcher.log" 2>&1; then
    log "Native MCP runtime-contract source = GREEN"
    return 0
  fi
  log "FOUT: Native MCP runtime-contract hotfix = RED"
  return 1
}

process_native_mcp_runtime_guard(){
  [ -f "$NATIVE_MCP_GUARD" ] || { log "FOUT: native MCP runtime guard ontbreekt"; return 1; }
  command -v python3 >/dev/null 2>&1 || return 1
  rc=0
  python3 "$NATIVE_MCP_GUARD" --root "$ROOT" >> "$LOGDIR/release_watcher.log" 2>&1 || rc=$?
  [ "$rc" -eq 0 ] && { log "Native MCP runtime fingerprint = GREEN"; return 0; }
  [ "$rc" -eq 3 ] && { log "Native MCP runtime fingerprint = RELOAD_REQUIRED"; return 1; }
  log "FOUT: native MCP runtime guard rc=$rc"
  return 1
}

process_native_mcp_reload(){
  [ -f "$NATIVE_MCP_RELOAD_REQUEST" ] || return 0
  [ -f "$NATIVE_MCP_RELOAD_EXECUTOR" ] || { log "FOUT: native MCP reload executor ontbreekt"; return 1; }
  command -v python3 >/dev/null 2>&1 || return 1
  # Een oud result mag nooit een nieuw request als verwerkt laten lijken.
  rm -f "$NATIVE_MCP_RELOAD_RESULT" 2>/dev/null || return 1
  rc=0
  run_bounded 120 python3 -c 'import sys; from pathlib import Path; sys.path.insert(0, sys.argv[2]); import native_mcp_reload_executor as m; m.run(Path(sys.argv[1]))' "$ROOT" "$PROJECT/tools" >> "$LOGDIR/release_watcher.log" 2>&1 || rc=$?
  if [ -f "$NATIVE_MCP_RELOAD_RESULT" ]; then rm -f "$NATIVE_MCP_RELOAD_REQUEST" 2>/dev/null || true; fi
  [ "$rc" -eq 0 ] && { log "Native MCP beschermde reload = GREEN"; return 0; }
  log "FOUT: native MCP beschermde reload rc=$rc"
  return 1
}

process_canonical_roadmap_migration(){
  [ -f "$CANONICAL_ROADMAP_MIGRATION" ] || { log "FOUT: canonical roadmap migration helper ontbreekt"; return 1; }
  [ -f "$CANONICAL_ROADMAP" ] || { log "FOUT: canonical roadmap bron ontbreekt"; return 1; }
  command -v python3 >/dev/null 2>&1 || return 1
  TMP_STATE="$CANONICAL_ROADMAP_MIGRATION_STATE.tmp.$$"
  rc=0
  run_bounded 20 python3 "$CANONICAL_ROADMAP_MIGRATION" --path "$CANONICAL_ROADMAP" > "$TMP_STATE" 2>&1 || rc=$?
  mv "$TMP_STATE" "$CANONICAL_ROADMAP_MIGRATION_STATE"
  [ "$rc" -eq 0 ] && { log "Canonical roadmap persist+readback = GREEN"; return 0; }
  log "FOUT: canonical roadmap migration/persistence rc=$rc"
  return 1
}

process_post_release_maintenance_transition(){
  [ -f "$POST_RELEASE_MODE_HELPER" ] || return 0
  command -v python3 >/dev/null 2>&1 || return 1
  if python3 "$POST_RELEASE_MODE_HELPER" --root "$ROOT" >> "$LOGDIR/release_watcher.log" 2>&1; then
    log "Post-release mode-transition gecontroleerd"
    return 0
  fi
  log "FOUT: post-release mode-transition mislukt"
  return 1
}

process_nas_cr_capability_probe(){
  mkdir -p "$NAS_CR_LOCAL_DIR" || { log "FOUT: NAS CR capabilitymap niet maakbaar"; return 1; }
  [ -f "$NAS_CR_LOCAL_PROBE" ] || { log "FOUT: NAS CR capability probe ontbreekt"; return 1; }
  command -v python3 >/dev/null 2>&1 || { log "FOUT: NAS CR capability probe vereist python3"; return 1; }
  if python3 "$NAS_CR_LOCAL_PROBE" --root "$ROOT" >> "$LOGDIR/release_watcher.log" 2>&1; then
    log "NAS CR lokale Docker capability = GREEN"
    return 0
  fi
  log "FOUT: NAS CR lokale Docker capability = RED"
  return 1
}

process_project_cr_local(){
  [ -f "$PROJECT_CR_LOCAL_REQUEST" ] || return 0
  if ! process_cr_standard_hotfix; then
    log "FOUT: EnergieProject CR geweigerd omdat CR-standaardhotfix niet GREEN is"
    return 1
  fi
  if ! process_native_mcp_runtime_guard; then
    log "FOUT: EnergieProject CR wacht op native-MCP runtime agreement"
    return 1
  fi
  [ -f "$PROJECT_CR_LOCAL_EXECUTOR" ] || { log "FOUT: EnergieProject CR lokale executor ontbreekt"; return 1; }
  command -v python3 >/dev/null 2>&1 || { log "FOUT: EnergieProject CR lokale executor vereist python3"; return 1; }
  rc=0
  run_bounded "$PROJECT_CR_LOCAL_TIMEOUT" python3 "$PROJECT_CR_LOCAL_EXECUTOR" --root "$ROOT" >> "$LOGDIR/release_watcher.log" 2>&1 || rc=$?
  [ "$rc" -eq 0 ] && { log "EnergieProject CR lokale executor = GREEN"; return 0; }
  log "FOUT: EnergieProject CR lokale executor rc=$rc; resultaat blijft beschikbaar"
  return "$rc"
}

process_nas_container_cr_local(){
  [ -f "$NAS_CR_LOCAL_REQUEST" ] || return 0
  if ! process_cr_standard_hotfix; then
    log "FOUT: NAS Container CR geweigerd omdat CR-standaardhotfix niet GREEN is"
    return 1
  fi
  [ -f "$NAS_CR_LOCAL_EXECUTOR" ] || { log "FOUT: NAS CR lokale executor ontbreekt"; return 1; }
  command -v python3 >/dev/null 2>&1 || { log "FOUT: NAS CR lokale executor vereist python3"; return 1; }
  rc=0
  run_bounded "$NAS_CR_LOCAL_TIMEOUT" python3 "$NAS_CR_LOCAL_EXECUTOR" --root "$ROOT" >> "$LOGDIR/release_watcher.log" 2>&1 || rc=$?
  if [ "$rc" -eq 0 ]; then
    log "NAS Container CR lokale executor = GREEN"
    return 0
  fi
  log "FOUT: NAS Container CR lokale executor rc=$rc; resultaat blijft beschikbaar"
  return "$rc"
}

process_project_clearup_move(){
  [ -f "$PROJECT_CLEARUP_REQUEST" ] || return 0
  if ! command -v python3 >/dev/null 2>&1; then
    log "FOUT: CLEARUP move request wacht; python3 ontbreekt in watchercontainer"
    return 1
  fi
  [ -f "$PROJECT_CLEARUP_EXECUTOR" ] || { log "FOUT: CLEARUP move executor ontbreekt: $PROJECT_CLEARUP_EXECUTOR"; return 1; }

  rc=0
  run_bounded "$PROJECT_CLEARUP_HELPER_TIMEOUT" python3 "$PROJECT_CLEARUP_EXECUTOR" \
      --root "$ROOT" \
      --request "$PROJECT_CLEARUP_REQUEST" \
      --result "$PROJECT_CLEARUP_RESULT" >> "$LOGDIR/release_watcher.log" 2>&1 || rc=$?

  if [ -f "$PROJECT_CLEARUP_RESULT" ]; then
    rm -f "$PROJECT_CLEARUP_REQUEST" 2>/dev/null || log "WAARSCHUWING: CLEARUP move request kon na resultaat niet worden verwijderd"
  fi

  if [ "$rc" -eq 0 ]; then
    log "CLEARUP watcher-executor afgerond"
    return 0
  fi
  log "FOUT: CLEARUP watcher-executor status rc=$rc; resultaat blijft beschikbaar"
  return "$rc"
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

  if run_bounded "$MAINTENANCE_HELPER_TIMEOUT" python3 "$CRASH_CLEANUP_HELPER" \
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
    atomic_swap_allows_release_ingress || { log "WACHT: atomic swap blokkeert release-ingress"; exit 1; }
    run_installer; exit $?;;
  run) ;;
  *) echo "Gebruik: $0 [run|once|status|stop]" >&2; exit 2;;
esac

# Cross-namespace singleton-claim. PID's zijn niet betrouwbaar tussen QNAP-host
# en Docker namespaces; de gedeelde heartbeat bepaalt daarom of de lock actief is.
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
STARTUP_DEGRADED=""
mark_startup_degraded(){
  item="$1"
  if [ -n "$STARTUP_DEGRADED" ]; then STARTUP_DEGRADED="$STARTUP_DEGRADED,$item"; else STARTUP_DEGRADED="$item"; fi
}
if [ -f "$CLEARUP_PREPARE" ] && sh "$CLEARUP_PREPARE" "$ROOT" >/dev/null 2>&1; then
  log "CLEARUP-root startup-preflight = OK"
else
  mark_startup_degraded "clearup-root-bootstrap"
  log "WAARSCHUWING: CLEARUP-root startup-preflight mislukt; watcher blijft actief, CLEARUP blijft fail-closed"
fi
touch_heartbeat
log "Release watcher gestart; interval=${INTERVAL}s"

if ! process_canonical_roadmap_migration; then mark_startup_degraded "canonical-roadmap-persistence"; fi

if ! process_post_release_maintenance_transition; then mark_startup_degraded "post-release-mode-transition"; fi

if process_mcp_guard_hotfix; then
  log "MCP hotfix startupcontrole = OK"
else
  mark_startup_degraded "mcp-system-path-hotfix"
fi

if process_cr_standard_hotfix; then
  log "CR-standaardhotfix startupcontrole = OK"
else
  mark_startup_degraded "cr-standard-hotfix"
fi

if process_watcher_container_contract; then
  log "Watcher container-contract startupcontrole = OK"
else
  mark_startup_degraded "watcher-container-recreate-required"
fi

if ! process_native_mcp_runtime_contract_hotfix; then mark_startup_degraded "native-mcp-runtime-contract"; fi

if process_native_mcp_runtime_guard; then
  log "Native MCP runtime startupcontrole = OK"
else
  mark_startup_degraded "native-mcp-reload-required"
fi

if process_nas_cr_capability_probe; then
  log "NAS CR capability startupcontrole = OK"
else
  mark_startup_degraded "nas-cr-local-capability"
fi

if ! cleanup_processed_releases_on_start; then
  mark_startup_degraded "processed-retention"
fi
if [ -n "$STARTUP_DEGRADED" ]; then
  write_status "MAINTENANCE_FAILED" "$STARTUP_DEGRADED; watcher blijft actief"
else
  write_status "WATCHER_ACTIVE" "startup-retention-ok keep=${PROCESSED_RETENTION}; startup-gates-ok"
fi

while :; do
  touch_heartbeat

  if mode_allows maintenance_requests; then
    process_native_mcp_reload || true
    process_native_mcp_runtime_guard || true
    process_project_cr_local || true
    process_nas_container_cr_local || true
    process_project_clearup_move || true
    process_crash_recovery_cleanup || true
  fi

  if mode_allows release_ingress && atomic_swap_allows_release_ingress; then
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
