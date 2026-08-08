#!/bin/sh
set -eu

if [ -n "${ENERGIE_SHARE:-}" ]; then
  SHARE="$ENERGIE_SHARE"
elif [ -d "/share/AI Projecten/EnergieProject" ]; then
  SHARE="/share/AI Projecten"
else
  SHARE="/share/Energie_NAS"
fi
PROJECT="$SHARE/EnergieProject"
INBOX="$SHARE/EnergieProject_Inbox"
INCOMING="$INBOX/incoming"
PROCESSING="$INBOX/processing"
PROCESSED="$INBOX/processed"
FAILED="$INBOX/failed"
BACKUPS="$SHARE/EnergieProject_Backups"
LOCK="$INBOX/.installer.lock"
REQUIRED="README.md INSTALL.md CHANGELOG.md MANIFEST.sha256 SHA256SUMS.json repository.yaml VERSIE.txt"

# Safety rule: never run the live installer from inside the worktree that it replaces.
# If invoked from the project, copy to /tmp and re-exec before touching the worktree.
if [ "${ENERGIE_INSTALLER_REEXEC:-0}" != "1" ]; then
  case "$0" in
    "$PROJECT"/*)
      TMP_SELF="/tmp/energie_release_installer.$$.sh"
      cp "$0" "$TMP_SELF" || { echo "FOUT: installer kon zichzelf niet naar /tmp kopieren" >&2; exit 1; }
      chmod 700 "$TMP_SELF" || true
      export ENERGIE_INSTALLER_REEXEC=1
      exec sh "$TMP_SELF" "$@"
      ;;
  esac
fi

ZIP_WORK=""
STAGE=""
RESTORE_STAGE=""
PREFLIGHT=""
BACKUP=""
BASE_COMMIT=""
GIT_AVAILABLE=0
WORKTREE_REPLACED=0

log(){ printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
WATCHER_PIDFILE="$INBOX/.watcher.pid"
schedule_watcher_refresh(){
  [ -f "$WATCHER_PIDFILE" ] || return 0
  WATCHER_PID="$(cat "$WATCHER_PIDFILE" 2>/dev/null || true)"
  case "$WATCHER_PID" in ''|*[!0-9]*) return 0;; esac
  kill -0 "$WATCHER_PID" 2>/dev/null || return 0
  if command -v nohup >/dev/null 2>&1; then
    nohup sh -c "sleep 2; kill '$WATCHER_PID' 2>/dev/null || true" >/dev/null 2>&1 &
  else
    ( sleep 2; kill "$WATCHER_PID" 2>/dev/null || true ) >/dev/null 2>&1 &
  fi
  log "Watcher-refresh gepland; QNAP cron start daarna automatisch de nieuw geïnstalleerde watcher"
}
cleanup(){
  [ -n "$PREFLIGHT" ] && rm -rf "$PREFLIGHT" 2>/dev/null || true
  [ -n "$RESTORE_STAGE" ] && rm -rf "$RESTORE_STAGE" 2>/dev/null || true
  [ -n "$STAGE" ] && rm -rf "$STAGE" 2>/dev/null || true
  rmdir "$LOCK" 2>/dev/null || true
}

copy_tree_no_metadata(){
  SRC=$1
  DST=$2
  # Intentionally use plain recursive copy without metadata preservation. QNAP shares may
  # reject ownership/timestamp preservation even though normal file writes work.
  cp -R "$SRC"/. "$DST"/
}

restore_backup(){
  [ "$WORKTREE_REPLACED" -eq 1 ] || return 0
  [ -n "$BACKUP" ] && [ -f "$BACKUP" ] || { log "FOUT: rollback vereist maar backup ontbreekt"; return 1; }
  log "Rollback: volledige vorige worktree herstellen uit $(basename "$BACKUP")"

  # Extract on /tmp first. This keeps tar from trying to restore directory
  # timestamps directly on the QNAP project share (known to return EPERM).
  RESTORE_STAGE="$(mktemp -d /tmp/energie-restore.XXXXXX)" || return 1
  tar -xzf "$BACKUP" -C "$RESTORE_STAGE" || return 1

  find "$PROJECT" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} + || return 1
  copy_tree_no_metadata "$RESTORE_STAGE" "$PROJECT" || return 1
  rm -rf "$RESTORE_STAGE" || true
  RESTORE_STAGE=""

  if [ "$GIT_AVAILABLE" -eq 1 ] && [ -n "$BASE_COMMIT" ]; then
    cd "$PROJECT"
    git reset --hard "$BASE_COMMIT" >/dev/null 2>&1 || return 1
    git config core.filemode false
  fi
  WORKTREE_REPLACED=0
  log "Rollback: herstel uit backup voltooid"
}

fail(){
  MSG="$*"
  if [ "$WORKTREE_REPLACED" -eq 1 ]; then
    restore_backup || log "FOUT: automatische rollback kon niet volledig worden afgerond"
  fi
  log "FOUT: $MSG"
  [ -n "$ZIP_WORK" ] && [ -f "$ZIP_WORK" ] && mv "$ZIP_WORK" "$FAILED/" 2>/dev/null || true
  cleanup
  exit 1
}

trap 'cleanup' EXIT INT TERM

mkdir -p "$INCOMING" "$PROCESSING" "$PROCESSED" "$FAILED" "$BACKUPS"
mkdir "$LOCK" 2>/dev/null || { log "FOUT: installer is al actief"; exit 1; }
log "FASE 1/8: inboxcontrole"

# A ZIP left in processing while no installer lock existed is an orphan from a
# previously interrupted/failed run. Quarantine it before accepting a new release.
set -- "$PROCESSING"/*.zip
if [ -e "$1" ]; then
  for orphan in "$PROCESSING"/*.zip; do
    [ -e "$orphan" ] || continue
    log "HERSTEL: verweesde processing-ZIP naar failed: $(basename "$orphan")"
    mv "$orphan" "$FAILED/" || fail "verweesde processing-ZIP kon niet naar failed"
  done
fi

set -- "$INCOMING"/*.zip
[ -e "$1" ] || { log "Geen release-ZIP in incoming."; exit 0; }
[ "$#" -eq 1 ] || fail "verwacht exact één ZIP in incoming, gevonden: $#"
ZIP="$1"
ZIP_WORK="$PROCESSING/$(basename "$ZIP")"
mv "$ZIP" "$ZIP_WORK"
log "Release gevonden: $(basename "$ZIP_WORK")"

log "FASE 2/8: ZIP- en releasevalidatie"
unzip -t "$ZIP_WORK" >/dev/null 2>&1 || fail "ZIP-integriteit ongeldig"
LIST="$(unzip -l "$ZIP_WORK" | awk '{print $4}')"
for f in $REQUIRED; do printf '%s\n' "$LIST" | grep -Fxq "$f" || fail "verplicht bestand ontbreekt: $f"; done

STAGE="$(mktemp -d /tmp/energie-release.XXXXXX)"
unzip -q "$ZIP_WORK" -d "$STAGE" || fail "uitpakken naar staging mislukt"
(cd "$STAGE" && sha256sum -c MANIFEST.sha256 >/dev/null) || fail "SHA256-validatie mislukt"
NEW_VERSION="$(tr -d '\r\n ' < "$STAGE/VERSIE.txt")"
[ -n "$NEW_VERSION" ] || fail "VERSIE.txt is leeg"
case "$NEW_VERSION" in *[!0-9.]*|'') fail "ongeldige versie in VERSIE.txt: $NEW_VERSION";; esac

log "FASE 3/8: huidige installatie controleren"
cd "$PROJECT"
CURRENT_VERSION="$(tr -d '\r\n ' < VERSIE.txt 2>/dev/null || true)"
if command -v git >/dev/null 2>&1 && [ -d "$PROJECT/.git" ]; then
  GIT_AVAILABLE=1
  DIRTY="$(git status --porcelain --untracked-files=all)"
  [ -z "$DIRTY" ] || fail "project bevat tracked of untracked lokale wijzigingen"
  BASE_COMMIT="$(git rev-parse HEAD)"
  REMOTE_MAIN="$(git ls-remote origin refs/heads/main | awk '{print $1}')"
  [ "$REMOTE_MAIN" = "$BASE_COMMIT" ] || fail "lokale main wijkt af van GitHub main; installatie gestopt"
  log "Git-modus actief: repository en GitHub main gecontroleerd"
else
  log "Git niet beschikbaar in deze QNAP-omgeving; veilige ZIP-installatiemodus actief"
fi

# QNAP preflight: prove create/copy/delete in the live project directory BEFORE
# a validated backup is followed by any destructive worktree operation.
PREFLIGHT="$PROJECT/.energie_release_preflight.$$"
mkdir "$PREFLIGHT" || fail "preflight: testmap maken in project mislukt"
printf 'qnap-preflight\n' > "$PREFLIGHT/source.txt" || fail "preflight: schrijven in project mislukt"
cp "$PREFLIGHT/source.txt" "$PREFLIGHT/copy.txt" || fail "preflight: normaal kopiëren in project mislukt"
[ "$(cat "$PREFLIGHT/copy.txt")" = "qnap-preflight" ] || fail "preflight: gekopieerde inhoud ongeldig"
rm -rf "$PREFLIGHT" || fail "preflight: verwijderen in project mislukt"
PREFLIGHT=""
log "QNAP preflight schrijven/kopiëren/verwijderen = OK"

log "FASE 4/8: volledige herstelbackup maken"
STAMP="$(date '+%Y%m%d-%H%M%S')"
BACKUP="$BACKUPS/EnergieProject_pre_${NEW_VERSION}_${STAMP}.tar.gz"
tar --exclude='./.git' -czf "$BACKUP" . || fail "backup maken mislukt"
tar -tzf "$BACKUP" >/dev/null 2>&1 || fail "backup-validatie mislukt"
log "Backup gevalideerd: $BACKUP"

log "FASE 5/8: release-worktree vervangen"
# WORKTREE_REPLACED becomes true BEFORE deletion, so any deletion failure triggers tar rollback.
WORKTREE_REPLACED=1
find "$PROJECT" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} + || fail "oude worktree leegmaken mislukt"
copy_tree_no_metadata "$STAGE" "$PROJECT" || fail "nieuwe release kopiëren mislukt"
cd "$PROJECT"
if [ "$GIT_AVAILABLE" -eq 1 ]; then git config core.filemode false; fi

log "FASE 6/8: post-installatiecontroles"
for f in $REQUIRED; do [ -f "$PROJECT/$f" ] || fail "post-installatiebestand ontbreekt: $f"; done
(cd "$PROJECT" && sha256sum -c MANIFEST.sha256 >/dev/null) || fail "post-installatie SHA256-validatie mislukt"
[ -f tools/release_installer.sh ] && sh -n tools/release_installer.sh || fail "shellsyntax release_installer.sh ongeldig"
[ -f tools/release_watcher.sh ] && sh -n tools/release_watcher.sh || fail "shellsyntax release_watcher.sh ongeldig"
if command -v python3 >/dev/null 2>&1 && python3 -m pytest --version >/dev/null 2>&1; then
  if [ -f tests/test_static.py ]; then
    python3 -m pytest -q tests/test_static.py || fail "statische tests mislukt"
    log "TESTSTATUS: pytest tests/test_static.py = OK"
  else
    log "TESTSTATUS: geen tests/test_static.py aanwezig"
  fi
else
  log "TESTSTATUS: pytest NIET UITGEVOERD - python3/pytest niet beschikbaar in deze installeromgeving"
  log "TESTSTATUS: vervangende controles ZIP/SHA256/verplichte bestanden/shellsyntax = OK"
fi

log "FASE 7/8: publicatie-afhandeling"
if [ "$GIT_AVAILABLE" -eq 1 ]; then
  git add -A
  if git diff --cached --quiet; then
    log "Geen inhoudelijke Git-wijziging; release $NEW_VERSION is al actief."
  else
    git commit -m "v${NEW_VERSION}: automated release inbox install" || fail "commit mislukt"
    NEW_COMMIT="$(git rev-parse HEAD)"
    if ! git push origin main; then
      REMOTE_AFTER="$(git ls-remote origin refs/heads/main | awk '{print $1}')"
      if [ "$REMOTE_AFTER" = "$NEW_COMMIT" ]; then
        log "Push gaf lokaal een fout, maar GitHub main bevat de nieuwe commit; push als geslaagd beschouwd."
      else
        fail "push mislukt en GitHub main bevat de nieuwe commit niet"
      fi
    fi
  fi
else
  log "Git-publicatie overgeslagen: git is niet geïnstalleerd op deze QNAP; release-installatie blijft zelfstandig werken"
fi

log "FASE 8/8: eindcontrole en archivering"
[ "$(tr -d '\r\n ' < "$PROJECT/VERSIE.txt")" = "$NEW_VERSION" ] || fail "eindcontrole mislukt: geïnstalleerde versie wijkt af"
if [ "$GIT_AVAILABLE" -eq 1 ]; then
  LOCAL_FINAL="$(git rev-parse HEAD)"
  REMOTE_FINAL="$(git ls-remote origin refs/heads/main | awk '{print $1}')"
  [ "$LOCAL_FINAL" = "$REMOTE_FINAL" ] || fail "eindcontrole mislukt: lokale en GitHub commit verschillen"
  [ -z "$(git status --porcelain --untracked-files=all)" ] || fail "eindcontrole mislukt: repository niet clean"
  FINAL_DETAIL="GitHub=$LOCAL_FINAL"
else
  FINAL_DETAIL="QNAP ZIP-modus zonder git"
fi
WORKTREE_REPLACED=0
mv "$ZIP_WORK" "$PROCESSED/"
ZIP_WORK=""
log "SUCCES: $CURRENT_VERSION -> $NEW_VERSION; $FINAL_DETAIL; ZIP gearchiveerd in processed."
schedule_watcher_refresh
