#!/bin/sh
set -eu

SHARE="${ENERGIE_SHARE:-/share/Energie_NAS}"
PROJECT="$SHARE/EnergieProject"
INBOX="$SHARE/EnergieProject_Inbox"
INCOMING="$INBOX/incoming"
PROCESSING="$INBOX/processing"
PROCESSED="$INBOX/processed"
FAILED="$INBOX/failed"
BACKUPS="$SHARE/EnergieProject_Backups"
LOCK="$INBOX/.installer.lock"
REQUIRED="README.md INSTALL.md CHANGELOG.md MANIFEST.sha256 SHA256SUMS.json repository.yaml VERSIE.txt"

ZIP_WORK=""
STAGE=""
BACKUP=""
BASE_COMMIT=""
WORKTREE_REPLACED=0
COMMIT_CREATED=0

log(){ printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
cleanup(){ [ -n "$STAGE" ] && rm -rf "$STAGE" 2>/dev/null || true; rmdir "$LOCK" 2>/dev/null || true; }

restore_backup(){
  [ "$WORKTREE_REPLACED" -eq 1 ] || return 0
  [ -n "$BACKUP" ] && [ -f "$BACKUP" ] || { log "FOUT: rollback vereist maar backup ontbreekt"; return 1; }
  log "Rollback: volledige vorige worktree herstellen uit $(basename "$BACKUP")"
  find "$PROJECT" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} + || return 1
  tar -xzf "$BACKUP" -C "$PROJECT" || return 1
  if [ -n "$BASE_COMMIT" ]; then
    cd "$PROJECT"
    git reset --hard "$BASE_COMMIT" >/dev/null 2>&1 || return 1
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

log "FASE 3/8: huidige repository controleren"
cd "$PROJECT"
DIRTY="$(git status --porcelain --untracked-files=all)"
[ -z "$DIRTY" ] || fail "project bevat tracked of untracked lokale wijzigingen"
BASE_COMMIT="$(git rev-parse HEAD)"
CURRENT_VERSION="$(tr -d '\r\n ' < VERSIE.txt 2>/dev/null || true)"
REMOTE_MAIN="$(git ls-remote origin refs/heads/main | awk '{print $1}')"
[ "$REMOTE_MAIN" = "$BASE_COMMIT" ] || fail "lokale main wijkt af van GitHub main; installatie gestopt"

log "FASE 4/8: volledige herstelbackup maken"
STAMP="$(date '+%Y%m%d-%H%M%S')"
BACKUP="$BACKUPS/EnergieProject_pre_${NEW_VERSION}_${STAMP}.tar.gz"
tar --exclude='./.git' -czf "$BACKUP" . || fail "backup maken mislukt"
tar -tzf "$BACKUP" >/dev/null 2>&1 || fail "backup-validatie mislukt"
log "Backup gevalideerd: $BACKUP"

log "FASE 5/8: release-worktree vervangen"
find "$PROJECT" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} + || fail "oude worktree leegmaken mislukt"
WORKTREE_REPLACED=1
cp -a "$STAGE"/. "$PROJECT"/ || fail "nieuwe release kopiëren mislukt"
git config core.filemode false

log "FASE 6/8: post-installatiecontroles"
for f in $REQUIRED; do [ -f "$PROJECT/$f" ] || fail "post-installatiebestand ontbreekt: $f"; done
(cd "$PROJECT" && sha256sum -c MANIFEST.sha256 >/dev/null) || fail "post-installatie SHA256-validatie mislukt"
if [ -f tools/release_installer.sh ]; then
  sh -n tools/release_installer.sh || fail "shellsyntax release_installer.sh ongeldig"
fi
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

log "FASE 7/8: Git commit en push"
git add -A
if git diff --cached --quiet; then
  log "Geen inhoudelijke wijziging; release $NEW_VERSION is al actief."
else
  git commit -m "v${NEW_VERSION}: automated release inbox install" || fail "commit mislukt"
  COMMIT_CREATED=1
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

log "FASE 8/8: eindcontrole en archivering"
LOCAL_FINAL="$(git rev-parse HEAD)"
REMOTE_FINAL="$(git ls-remote origin refs/heads/main | awk '{print $1}')"
[ "$LOCAL_FINAL" = "$REMOTE_FINAL" ] || fail "eindcontrole mislukt: lokale en GitHub commit verschillen"
[ -z "$(git status --porcelain --untracked-files=all)" ] || fail "eindcontrole mislukt: repository niet clean"
WORKTREE_REPLACED=0
mv "$ZIP_WORK" "$PROCESSED/"
ZIP_WORK=""
log "SUCCES: $CURRENT_VERSION -> $NEW_VERSION; GitHub=$LOCAL_FINAL; ZIP gearchiveerd in processed."
