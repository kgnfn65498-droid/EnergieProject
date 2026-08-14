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
PROCESSING="$INBOX/processing"
PROCESSED="$INBOX/processed"
FAILED="$INBOX/failed"
BACKUPS="$ROOT/Backups"
BACKUP_RETENTION="${ENERGIE_BACKUP_RETENTION:-3}"
PROCESSED_RETENTION="${ENERGIE_PROCESSED_RETENTION:-3}"
LOCK="$INBOX/.installer.lock"
PROCESSING_STALE_SECONDS="${ENERGIE_PROCESSING_STALE_SECONDS:-600}"
REQUIRED="README.md INSTALL.md CHANGELOG.md MANIFEST.sha256 SHA256SUMS.json repository.yaml VERSIE.txt"
ZIP_HELPER="$PROJECT/tools/release_zip.py"
HA_PUBLICATION_REQUIRED="$INBOX/ha_publication_required.json"

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
  log "Watcher-refresh gepland; actieve watcher schakelt autonoom over op de nieuw geïnstalleerde release"
}
cleanup(){
  [ -n "$PREFLIGHT" ] && rm -rf "$PREFLIGHT" 2>/dev/null || true
  [ -n "$RESTORE_STAGE" ] && rm -rf "$RESTORE_STAGE" 2>/dev/null || true
  [ -n "$STAGE" ] && rm -rf "$STAGE" 2>/dev/null || true
  rmdir "$LOCK" 2>/dev/null || true
}

zip_test(){
  ZIP_PATH=$1
  if command -v python3 >/dev/null 2>&1 && [ -f "$ZIP_HELPER" ]; then
    python3 "$ZIP_HELPER" test "$ZIP_PATH" >/dev/null 2>&1
  else
    unzip -t "$ZIP_PATH" >/dev/null 2>&1
  fi
}

zip_list(){
  ZIP_PATH=$1
  if command -v python3 >/dev/null 2>&1 && [ -f "$ZIP_HELPER" ]; then
    python3 "$ZIP_HELPER" list "$ZIP_PATH"
  else
    unzip -l "$ZIP_PATH" | awk '{print $4}'
  fi
}

zip_extract(){
  ZIP_PATH=$1
  DEST=$2
  if command -v python3 >/dev/null 2>&1 && [ -f "$ZIP_HELPER" ]; then
    python3 "$ZIP_HELPER" extract "$ZIP_PATH" "$DEST"
  else
    unzip -q "$ZIP_PATH" -d "$DEST"
  fi
}

copy_tree_no_metadata(){
  SRC=$1
  DST=$2
  # Intentionally use plain recursive copy without metadata preservation. QNAP shares may
  # reject ownership/timestamp preservation even though normal file writes work.
  cp -R "$SRC"/. "$DST"/
}

cleanup_old_backups(){
  case "$BACKUP_RETENTION" in
    ''|*[!0-9]*)
      log "WAARSCHUWING: ongeldige backupretentie '$BACKUP_RETENTION'; gebruik 3"
      BACKUP_RETENTION=3
      ;;
  esac
  [ "$BACKUP_RETENTION" -ge 1 ] 2>/dev/null || BACKUP_RETENTION=3

  set -- "$BACKUPS"/EnergieProject_pre_*.tar.gz
  [ -e "$1" ] || return 0

  OLD_BACKUPS="$(ls -1t "$BACKUPS"/EnergieProject_pre_*.tar.gz 2>/dev/null | tail -n +$((BACKUP_RETENTION + 1)) || true)"
  if [ -z "$OLD_BACKUPS" ]; then
    log "Backupretentie: maximaal $BACKUP_RETENTION; niets op te ruimen"
    return 0
  fi

  printf '%s\n' "$OLD_BACKUPS" | while IFS= read -r old_backup; do
    [ -n "$old_backup" ] || continue
    [ "$old_backup" = "$BACKUP" ] && continue
    if rm -f -- "$old_backup"; then
      log "Backupretentie: verwijderd $(basename "$old_backup")"
    else
      log "WAARSCHUWING: backupretentie kon $(basename "$old_backup") niet verwijderen"
    fi
  done

  log "Backupretentie toegepast: maximaal $BACKUP_RETENTION pre-release backups"
}


cleanup_processed_releases(){
  case "$PROCESSED_RETENTION" in
    ''|*[!0-9]*) PROCESSED_RETENTION=3 ;;
  esac
  [ "$PROCESSED_RETENTION" -ge 1 ] 2>/dev/null || PROCESSED_RETENTION=3

  COUNT="$(find "$PROCESSED" -maxdepth 1 -type f -name 'EnergieProject_v*.zip' 2>/dev/null | wc -l | tr -d ' ')"
  log "Processed-retentie: start count=$COUNT keep=$PROCESSED_RETENTION"
  [ "$COUNT" -gt "$PROCESSED_RETENTION" ] || {
    log "Processed-retentie: niets op te ruimen"
    return 0
  }

  RANKED="$(mktemp /tmp/energie-processed-ranked.XXXXXX)" || fail "processed-retentie: ranked tempfile mislukt"
  REMOVE="$(mktemp /tmp/energie-processed-remove.XXXXXX)" || {
    rm -f "$RANKED"
    fail "processed-retentie: remove tempfile mislukt"
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
      *[!0-9:]*|'') continue ;;
    esac
    printf '%09d.%09d.%09d %s\n' "$major" "$minor" "$patch" "$release_zip"
  done | sort -r > "$RANKED"

  tail -n +$((PROCESSED_RETENTION + 1)) "$RANKED" | cut -d' ' -f2- > "$REMOVE"
  while IFS= read -r old_release; do
    [ -n "$old_release" ] || continue
    rm -f -- "$old_release" || {
      rm -f "$RANKED" "$REMOVE"
      fail "processed-retentie: verwijderen mislukt: $(basename "$old_release")"
    }
    log "Processed-retentie: verwijderd $(basename "$old_release")"
  done < "$REMOVE"
  rm -f "$RANKED" "$REMOVE"

  AFTER="$(find "$PROCESSED" -maxdepth 1 -type f -name 'EnergieProject_v*.zip' 2>/dev/null | wc -l | tr -d ' ')"
  [ "$AFTER" -le "$PROCESSED_RETENTION" ] || fail "processed-retentie eindcontrole mislukt: count=$AFTER keep=$PROCESSED_RETENTION"
  log "Processed-retentie toegepast en gecontroleerd: count=$AFTER keep=$PROCESSED_RETENTION"
}


write_ha_publication_required(){
  TMP_PUBLICATION="$HA_PUBLICATION_REQUIRED.tmp.$$"
  cat > "$TMP_PUBLICATION" <<EOF
{"status":"publication_required","version":"$NEW_VERSION","repository":"https://github.com/kgnfn65498-droid/EnergieProject","branch":"main","reason":"qnap_zip_mode_without_git"}
EOF
  mv "$TMP_PUBLICATION" "$HA_PUBLICATION_REQUIRED"
  log "HA-publicatie vereist voor v$NEW_VERSION; marker=$HA_PUBLICATION_REQUIRED"
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

mkdir -p "$INCOMING" "$PROCESSING" "$PROCESSED" "$FAILED" "$LOGDIR" "$BACKUPS"

# v32.0.36: backups blijven via QNAP Finder/SMB door de beheerder verwijderbaar.
chgrp everyone "$BACKUPS" 2>/dev/null || true
chmod 2775 "$BACKUPS" || fail "Backups-map groepsbeheer instellen mislukt"
mkdir "$LOCK" 2>/dev/null || { log "FOUT: installer is al actief"; exit 1; }
log "FASE 1/8: inboxcontrole"

# Een processing-ZIP is niet automatisch verweesd. Een tweede watcher kan enkele
# seconden later starten terwijl de eerste installer de ZIP al heeft geclaimd.
# Alleen duidelijk oude processing-ZIP's worden in quarantaine gezet.
now_epoch="$(date +%s)"
set -- "$PROCESSING"/*.zip
if [ -e "$1" ]; then
  for orphan in "$PROCESSING"/*.zip; do
    [ -e "$orphan" ] || continue
    modified_epoch="$(date -r "$orphan" +%s 2>/dev/null || echo "$now_epoch")"
    age_seconds=$((now_epoch - modified_epoch))
    if [ "$age_seconds" -ge "$PROCESSING_STALE_SECONDS" ]; then
      log "HERSTEL: oude processing-ZIP (${age_seconds}s) naar failed: $(basename "$orphan")"
      mv "$orphan" "$FAILED/" || fail "oude processing-ZIP kon niet naar failed"
    else
      log "WACHT: processing-ZIP is actief/recent (${age_seconds}s): $(basename "$orphan")"
    fi
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
zip_test "$ZIP_WORK" || fail "ZIP-integriteit ongeldig"
LIST="$(zip_list "$ZIP_WORK")"
for f in $REQUIRED; do printf '%s\n' "$LIST" | grep -Fxq "$f" || fail "verplicht bestand ontbreekt: $f"; done

STAGE="$(mktemp -d /tmp/energie-release.XXXXXX)"
zip_extract "$ZIP_WORK" "$STAGE" || fail "uitpakken naar staging mislukt"
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
chgrp everyone "$BACKUP" 2>/dev/null || true
chmod 660 "$BACKUP" || fail "pre-release backup groepsrechten instellen mislukt"
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
  write_ha_publication_required
  log "Git-publicatie niet lokaal mogelijk; NAS-release is geïnstalleerd maar HA-update wacht op externe GitHub-publicatie"
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
CANONICAL_PROCESSED="$PROCESSED/EnergieProject_v${NEW_VERSION}.zip"
rm -f "$CANONICAL_PROCESSED"
mv "$ZIP_WORK" "$CANONICAL_PROCESSED"
ZIP_WORK=""
cleanup_old_backups
cleanup_processed_releases
log "SUCCES: $CURRENT_VERSION -> $NEW_VERSION; $FINAL_DETAIL; ZIP canoniek gearchiveerd als EnergieProject_v${NEW_VERSION}.zip in processed."
schedule_watcher_refresh
