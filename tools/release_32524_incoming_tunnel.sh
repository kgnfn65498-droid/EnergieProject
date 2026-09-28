#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/../../../../App/VERSIE.txt" ]; then
  ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/../../../.." && pwd)"
elif [ -f "$SCRIPT_DIR/../VERSIE.txt" ]; then
  ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)"
else
  echo "RELEASE_32524_TUNNEL_RED:project_root_not_found" >&2
  exit 1
fi

LIVE_EXPECTED="32.5.23"
WATCHER="energie-release-watcher"
CP="energie-control-plane"
CP_ROOT="$ROOT/Data/03_Systeem/Projectmanager/ControlPlane"
CANON_QNAP="$CP_ROOT/qnap_control_plane_bootstrap.py"
CURRENT_QNAP_SHA="203bfef028a79445f18a0d3ac714f2488bce26a3a948916dfc3ef7797202fa2c"
CARRIER="$ROOT/Data/03_Systeem/Projectmanager/Maintenance/RecoveryCarrier32_5_24/qnap_control_plane_bootstrap.py"
CARRIER_SHA="f3453e9029a2cf549db748559051fd6b67fc1d9f7e19097e5fa61c853de6cd3e"
CP_SHA="76386dd8eb032eadca41b2b180de1d38556be923530065e366e0a65f43121ee6"
BRIDGE_SHA="044df2390c4c911ecb725539726a1e1b219ecf36900d3ff9ce6a7d659f766c6f"
AUTH_SHA="db14b9d2751999c83e83a313cae0f3a4bb89a627be38d308907f14be819b7021"
EXPECTED_FP="781274e8cbf9096e0c50a35b55cc0d9f2fd8090ab87916884167cda8e0e95036"
STALE_ATTEMPT_FP="0dc5d7d08afedd2538b667cf973b8ff21839bde3456b2aae2b3179d3faccd325"
ATTEMPT="$ROOT/Data/03_Systeem/Projectmanager/ReleaseController/control_plane_restart_attempt.json"
CANON_RUNTIME="$ROOT/Data/03_Systeem/Projectmanager/ControlPlane/Runtime/runtime.json"
RC_RUNTIME="$ROOT/Data/03_Systeem/Projectmanager/ReleaseController/runtime.json"
RC_CURRENT="$ROOT/Data/03_Systeem/Projectmanager/ReleaseController/current.json"
STAMP="$(date +%Y%m%dT%H%M%S)"
REC="$ROOT/Data/03_Systeem/Projectmanager/Maintenance/IncomingTunnel32_5_24_$STAMP"
STATE="$REC/state.txt"

sha(){ sha256sum "$1" | awk '{print $1}'; }
die(){ echo "RELEASE_32524_TUNNEL_RED:$1" >&2; exit 1; }
mark(){ printf '%s\n' "$1" > "$STATE"; sync "$STATE" 2>/dev/null || true; }
exists(){ "$DOCKER" inspect "$1" >/dev/null 2>&1; }
running(){ [ "$("$DOCKER" inspect -f '{{.State.Running}}' "$1" 2>/dev/null || true)" = "true" ]; }
healthy(){ [ "$("$DOCKER" inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$1" 2>/dev/null || true)" = "healthy" ]; }
zip_count(){ n=0; for f in "$1/"*.zip; do [ -e "$f" ] || continue; n=$((n+1)); done; printf '%s' "$n"; }

CHECK_ONLY=0
case "${1:-}" in
  "") ;;
  --check-only) CHECK_ONLY=1 ;;
  *) die "unsupported_argument:$1" ;;
esac

[ -d "$ROOT/App" ] || die "project_root_invalid"
[ "$(tr -d '\r\n ' < "$ROOT/App/VERSIE.txt" 2>/dev/null || true)" = "$LIVE_EXPECTED" ] || die "live_version_not_$LIVE_EXPECTED"
[ "$(zip_count "$ROOT/Inbox/incoming")" -eq 0 ] || die "incoming_must_be_empty_before_tunnel"
[ "$(zip_count "$ROOT/Inbox/processing")" -eq 0 ] || die "processing_must_be_empty_before_tunnel"
[ -f "$CANON_QNAP" ] && [ ! -L "$CANON_QNAP" ] && [ "$(sha "$CANON_QNAP")" = "$CURRENT_QNAP_SHA" ] || die "qnap_control_plane_source_mismatch"
[ -f "$CARRIER" ] && [ ! -L "$CARRIER" ] && [ "$(sha "$CARRIER")" = "$CARRIER_SHA" ] || die "recovery_carrier_mismatch"
[ -f "$CP_ROOT/control_plane.py" ] && [ "$(sha "$CP_ROOT/control_plane.py")" = "$CP_SHA" ] || die "control_plane_source_mismatch"
[ -f "$CP_ROOT/control_plane_release_bridge.py" ] && [ "$(sha "$CP_ROOT/control_plane_release_bridge.py")" = "$BRIDGE_SHA" ] || die "control_plane_bridge_mismatch"
[ -f "$CP_ROOT/release_scoped_auth.py" ] && [ "$(sha "$CP_ROOT/release_scoped_auth.py")" = "$AUTH_SHA" ] || die "control_plane_auth_mismatch"
[ -f "$ATTEMPT" ] && [ ! -L "$ATTEMPT" ] || die "restart_attempt_missing"
grep -Fq '"status": "ATTEMPTING"' "$ATTEMPT" || die "restart_attempt_not_attempting"
grep -Fq "$STALE_ATTEMPT_FP" "$ATTEMPT" || die "restart_attempt_fingerprint_unexpected"
[ -f "$RC_RUNTIME" ] && grep -Fq 'control_plane_prepare_failed' "$RC_RUNTIME" && grep -Fq '"status": "BLOCKED"' "$RC_RUNTIME" || die "release_controller_expected_blocker_missing"
[ -f "$RC_CURRENT" ] && grep -Fq '"to_version": "32.5.23"' "$RC_CURRENT" && grep -Fq '"phase": "COMPLETE"' "$RC_CURRENT" && grep -Fq '"status": "COMPLETE"' "$RC_CURRENT" || die "release_controller_current_not_32523_complete"

DOCKER="$(command -v docker 2>/dev/null || true)"
if [ -z "$DOCKER" ]; then
  for candidate in \
    "/share/CACHEDEV1_DATA/.qpkg/container-station/bin/docker" \
    "/share/CACHEDEV2_DATA/.qpkg/container-station/bin/docker" \
    "/share/Container/container-station-data/lib/docker/bin/docker" \
    "/usr/local/bin/docker"
  do
    if [ -x "$candidate" ]; then DOCKER="$candidate"; break; fi
  done
fi
[ -n "$DOCKER" ] || die "docker_cli_missing"
"$DOCKER" image inspect python:3.12-slim >/dev/null 2>&1 || die "control_plane_image_missing"
exists "$WATCHER" || die "release_watcher_container_missing"
running "$WATCHER" || die "release_watcher_not_running_preflight"

if [ "$CHECK_ONLY" -eq 1 ]; then
  echo "RELEASE_32524_TUNNEL_CHECK_ONLY_GREEN"
  exit 0
fi

mkdir -p "$REC" || die "evidence_dir_create_failed"
cp -p "$ATTEMPT" "$REC/control_plane_restart_attempt.before.json" || die "attempt_backup_failed"
cp -p "$CANON_QNAP" "$REC/qnap_control_plane_bootstrap.before.py" || die "canonical_qnap_backup_failed"
WATCHER_STOPPED=0
CP_MUTATED=0
ATTEMPT_RETIRED=0
SOURCE_REPLACED=0
PRESERVED_CURRENT=""
CURRENT_WAS_RUNNING=0

rollback(){
  set +e
  if exists "$WATCHER" && running "$WATCHER"; then "$DOCKER" stop -t 15 "$WATCHER" >/dev/null 2>&1 || true; fi
  if [ "$CP_MUTATED" -eq 1 ]; then
    if exists "$CP"; then "$DOCKER" rm -f "$CP" >/dev/null 2>&1; fi
    if [ -n "$PRESERVED_CURRENT" ] && exists "$PRESERVED_CURRENT"; then
      "$DOCKER" rename "$PRESERVED_CURRENT" "$CP" >/dev/null 2>&1 || true
      if [ "$CURRENT_WAS_RUNNING" -eq 1 ]; then "$DOCKER" start "$CP" >/dev/null 2>&1 || true; fi
    fi
  fi
  if [ "$ATTEMPT_RETIRED" -eq 1 ]; then cp -p "$REC/control_plane_restart_attempt.before.json" "$ATTEMPT" 2>/dev/null || true; fi
  if [ "$SOURCE_REPLACED" -eq 1 ]; then cp -p "$REC/qnap_control_plane_bootstrap.before.py" "$CANON_QNAP" 2>/dev/null || true; fi
  "$DOCKER" start "$WATCHER" >/dev/null 2>&1 || true
  mark "ROLLED_BACK"
}
trap 'rollback; echo "RELEASE_32524_TUNNEL_RED:interrupted" >&2; exit 1' HUP INT TERM

"$DOCKER" stop -t 30 "$WATCHER" >/dev/null 2>&1 || { rollback; die "watcher_stop_failed"; }
WATCHER_STOPPED=1
mark "WATCHER_STOPPED"

# Stop the release-controller writer before replacing canonical source.
# Otherwise its source-sync can race this recovery and restore the old qnap bootstrap.
cat "$CARRIER" > "$CANON_QNAP" || { rollback; die "install_recovery_carrier_failed"; }
SOURCE_REPLACED=1
[ "$(sha "$CANON_QNAP")" = "$CARRIER_SHA" ] || { rollback; die "recovery_carrier_readback_mismatch"; }
sleep 2
[ "$(sha "$CANON_QNAP")" = "$CARRIER_SHA" ] || { rollback; die "recovery_carrier_raced_after_watcher_stop"; }
mark "CANONICAL_SOURCE_READY"

if exists "$CP"; then
  if running "$CP"; then CURRENT_WAS_RUNNING=1; "$DOCKER" stop -t 15 "$CP" >/dev/null 2>&1 || { rollback; die "current_control_plane_stop_failed"; }; fi
  PRESERVED_CURRENT="${CP}-pre32524-${STAMP}"
  "$DOCKER" rename "$CP" "$PRESERVED_CURRENT" >/dev/null 2>&1 || { rollback; die "current_control_plane_preserve_failed"; }
fi
CP_MUTATED=1
mark "CANONICAL_NAME_FREE"

"$DOCKER" create \
  --name "$CP" --restart unless-stopped --network none --read-only \
  --security-opt no-new-privileges --cap-drop ALL \
  --cap-add DAC_OVERRIDE --cap-add DAC_READ_SEARCH --cap-add FOWNER \
  -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUNBUFFERED=1 \
  --label com.energie.component=control-plane --label com.energie.cr.required=true \
  --health-cmd 'python3 -c "import pathlib,socket; assert b'\''qnap_control_plane_bootstrap.py'\'' in pathlib.Path('\''/proc/1/cmdline'\'').read_bytes(); s=socket.socket(socket.AF_UNIX); s.settimeout(3); s.connect('\''/var/run/docker.sock'\''); s.close()"' \
  --health-interval 30s --health-timeout 5s --health-retries 3 --health-start-period 10s \
  --tmpfs /tmp:size=16m,mode=1777 \
  -v "$ROOT/Data/03_Systeem/Projectmanager/ControlPlane:/control-plane:ro" \
  -v "$ROOT/Inbox:/energy-inbox:ro" \
  -v "$ROOT/Data/03_Systeem/Projectmanager/RuntimeV2/approved_actions:/pm-approved:ro" \
  -v "$ROOT/Data/03_Systeem/Projectmanager/RuntimeEvidence:/runtime-evidence:ro" \
  -v "$ROOT/Data/03_Systeem/Projectmanager/ControlPlane/Runtime:/control-plane-runtime:rw" \
  -v "$ROOT/Data/03_Systeem/Projectmanager/ReleaseController:/release-controller:ro" \
  -v "$ROOT/Data/03_Systeem/Projectmanager/RuntimeEvidence/NativeMCP:/native-mcp-runtime:ro" \
  -v /var/run/docker.sock:/var/run/docker.sock:rw \
  python:3.12-slim python3 /control-plane/qnap_control_plane_bootstrap.py \
  --inbox /energy-inbox --approved-queue /pm-approved/queue.json \
  --runtime-evidence /runtime-evidence --runtime-root /control-plane-runtime \
  --security-root /control-plane-runtime --release-controller-root /release-controller \
  --native-mcp-runtime-root /native-mcp-runtime --host-project-root "$ROOT" --interval 2 \
  >/dev/null 2>&1 || { rollback; die "control_plane_create_failed"; }
"$DOCKER" start "$CP" >/dev/null 2>&1 || { rollback; die "control_plane_start_failed"; }
mark "NEW_CONTROL_PLANE_STARTED"

N=0
while [ "$N" -lt 90 ]; do
  if running "$CP" && healthy "$CP" && [ -f "$CANON_RUNTIME" ] \
     && grep -Fq "$EXPECTED_FP" "$CANON_RUNTIME" 2>/dev/null; then break; fi
  sleep 2; N=$((N+1))
done
[ "$N" -lt 90 ] || { rollback; die "canonical_control_plane_not_proven_within_180s"; }
mark "CONTROL_PLANE_PROVEN"

if [ -f "$ATTEMPT" ]; then
  mv "$ATTEMPT" "$REC/control_plane_restart_attempt.retired.json" || { rollback; die "attempt_retire_failed"; }
  ATTEMPT_RETIRED=1
fi
"$DOCKER" start "$WATCHER" >/dev/null 2>&1 || { rollback; die "watcher_start_failed"; }
WATCHER_STOPPED=0
mark "WATCHER_STARTED"

N=0
while [ "$N" -lt 60 ]; do
  if running "$WATCHER" && [ -f "$RC_RUNTIME" ] \
     && grep -Fq '"phase": "IDLE"' "$RC_RUNTIME" 2>/dev/null \
     && grep -Fq '"status": "IDLE"' "$RC_RUNTIME" 2>/dev/null \
     && ! grep -Fq 'control_plane_prepare_failed' "$RC_RUNTIME" 2>/dev/null; then break; fi
  sleep 2; N=$((N+1))
done
[ "$N" -lt 60 ] || { rollback; die "release_controller_not_idle_within_120s"; }
[ "$(zip_count "$ROOT/Inbox/incoming")" -eq 0 ] || { rollback; die "incoming_changed_during_tunnel"; }
[ "$(zip_count "$ROOT/Inbox/processing")" -eq 0 ] || { rollback; die "processing_changed_during_tunnel"; }
[ "$(tr -d '\r\n ' < "$ROOT/App/VERSIE.txt" 2>/dev/null || true)" = "$LIVE_EXPECTED" ] || { rollback; die "live_version_changed_during_tunnel"; }

mark "TUNNEL_GREEN"
trap - HUP INT TERM
echo "RELEASE_32524_TUNNEL_CONTROL_PLANE_GREEN"
echo "RELEASE_32524_TUNNEL_WATCHER_GREEN"
echo "RELEASE_32524_TUNNEL_RELEASE_CONTROLLER_IDLE_GREEN"
echo "RELEASE_32524_TUNNEL_INCOMING_READY_GREEN"
echo "RELEASE_32524_TUNNEL_GREEN"
echo "RECOVERY_EVIDENCE=$REC"
exit 0
