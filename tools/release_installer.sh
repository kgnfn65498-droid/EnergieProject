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
LOGDIR="$INBOX/logs"
BACKUPS="$ROOT/Backups"
BACKUP_RETENTION="${ENERGIE_BACKUP_RETENTION:-3}"
PROCESSED_RETENTION="${ENERGIE_PROCESSED_RETENTION:-3}"
LOCK="$INBOX/.installer.lock"
PROCESSING_STALE_SECONDS="${ENERGIE_PROCESSING_STALE_SECONDS:-600}"
REQUIRED="README.md INSTALL.md CHANGELOG.md MANIFEST.sha256 SHA256SUMS.json repository.yaml VERSIE.txt"
ZIP_HELPER="$PROJECT/tools/release_zip.py"
ATOMIC_SWAP="$PROJECT/tools/atomic_app_swap.py"
HA_PUBLICATION_REQUIRED="$INBOX/ha_publication_required.json"
RELEASE_HOLD_STATE="$INBOX/operating_mode/release_validation_hold.json"
POST_RELEASE_MAINTENANCE="$INBOX/operating_mode/post_release_maintenance_required.json"
PREVIOUS_RELEASE_HOLD_BACKUP=""
PREVIOUS_RELEASE_HOLD_EXISTED=0
RELEASE_HOLD_ARMED=0

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
BACKUP=""
BASE_COMMIT=""
GIT_AVAILABLE=0
WORKTREE_REPLACED=0
ATOMIC_SWAP_RUNNER=""
ATOMIC_SWAP_ACTIVE=0

log(){ printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
WATCHER_PIDFILE="$INBOX/.watcher.pid"
schedule_watcher_refresh(){
  log "Watcher-refresh gepland; actieve watcher schakelt autonoom over op de nieuw geïnstalleerde release"
}

write_post_release_maintenance_required(){
  mkdir -p "$INBOX/operating_mode" || return 1
  TMP_POST="$POST_RELEASE_MAINTENANCE.tmp.$$"
  cat > "$TMP_POST" <<EOF
{"schema":"energie_post_release_maintenance_v1","status":"REQUIRED","release_version":"$NEW_VERSION","from_version":"$CURRENT_VERSION","reason":"release_installed_live_acceptance_required","created_at":"$(date '+%Y-%m-%dT%H:%M:%S%z')"}
EOF
  mv "$TMP_POST" "$POST_RELEASE_MAINTENANCE" || { rm -f "$TMP_POST" 2>/dev/null || true; return 1; }
  return 0
}

cleanup(){
  [ -n "$STAGE" ] && rm -rf "$STAGE" 2>/dev/null || true
  [ -n "$ATOMIC_SWAP_RUNNER" ] && rm -f "$ATOMIC_SWAP_RUNNER" 2>/dev/null || true
  [ -n "$PREVIOUS_RELEASE_HOLD_BACKUP" ] && rm -f "$PREVIOUS_RELEASE_HOLD_BACKUP" 2>/dev/null || true
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


capture_previous_release_validation_hold(){
  [ -z "$PREVIOUS_RELEASE_HOLD_BACKUP" ] || return 0
  PREVIOUS_RELEASE_HOLD_BACKUP="$(mktemp /tmp/energie-release-hold-prev.XXXXXX)" || return 1
  if [ -f "$RELEASE_HOLD_STATE" ]; then
    cp "$RELEASE_HOLD_STATE" "$PREVIOUS_RELEASE_HOLD_BACKUP" || return 1
    PREVIOUS_RELEASE_HOLD_EXISTED=1
  else
    : > "$PREVIOUS_RELEASE_HOLD_BACKUP" || return 1
    PREVIOUS_RELEASE_HOLD_EXISTED=0
  fi
}

restore_previous_release_validation_hold(){
  [ "$RELEASE_HOLD_ARMED" -eq 1 ] || return 0
  if [ "$PREVIOUS_RELEASE_HOLD_EXISTED" -eq 1 ]; then
    mkdir -p "$INBOX/operating_mode" || return 1
    RESTORE_HOLD_TMP="$RELEASE_HOLD_STATE.tmp.restore.$$"
    cp "$PREVIOUS_RELEASE_HOLD_BACKUP" "$RESTORE_HOLD_TMP" || { rm -f "$RESTORE_HOLD_TMP" 2>/dev/null || true; return 1; }
    mv "$RESTORE_HOLD_TMP" "$RELEASE_HOLD_STATE" || { rm -f "$RESTORE_HOLD_TMP" 2>/dev/null || true; return 1; }
  else
    rm -f "$RELEASE_HOLD_STATE" || return 1
  fi
  RELEASE_HOLD_ARMED=0
  log "Vorige release validation hold hersteld na mislukte release"
}

write_release_validation_hold(){
  capture_previous_release_validation_hold || return 1
  mkdir -p "$INBOX/operating_mode" || return 1
  TMP_HOLD="$RELEASE_HOLD_STATE.tmp.$$"
  cat > "$TMP_HOLD" <<EOF
{"schema_version":1,"active":true,"release_version":"$NEW_VERSION","activated_at":"$(date '+%Y-%m-%dT%H:%M:%S%z')","activated_reason":"release_install","validation_status":"required","validation_checks":{},"reconcile_status":"required","released_at":"","released_by":"","emergency_release":false,"reasons":[]}
EOF
  mv "$TMP_HOLD" "$RELEASE_HOLD_STATE" || {
    rm -f "$TMP_HOLD" 2>/dev/null || true
    return 1
  }
  RELEASE_HOLD_ARMED=1
  log "Release validation hold actief voor v$NEW_VERSION; marker=$RELEASE_HOLD_STATE"
}


write_ha_publication_required(){
  PROCESSED_SHA256="$1"
  [ -d "$HA_PUBLICATION_REQUIRED" ] && return 1
  TMP_PUBLICATION="$HA_PUBLICATION_REQUIRED.tmp.$$"
  cat > "$TMP_PUBLICATION" <<EOF
{"status":"publication_required","version":"$NEW_VERSION","repository":"https://github.com/kgnfn65498-droid/EnergieProject","branch":"main","reason":"validated_qnap_release_ready_for_github","expected_previous_version":"$CURRENT_VERSION","expected_previous_manifest_sha256":"$CURRENT_MANIFEST_SHA256","target_manifest_sha256":"$TARGET_MANIFEST_SHA256","processed_zip":"EnergieProject_v$NEW_VERSION.zip","processed_zip_sha256":"$PROCESSED_SHA256"}
EOF
  mv "$TMP_PUBLICATION" "$HA_PUBLICATION_REQUIRED" || {
    rm -f "$TMP_PUBLICATION" 2>/dev/null || true
    return 1
  }
  [ -f "$HA_PUBLICATION_REQUIRED" ] || return 1
  grep -Fq "\"version\":\"$NEW_VERSION\"" "$HA_PUBLICATION_REQUIRED" || return 1
  log "HA-publicatiecontract gereed voor v$NEW_VERSION; marker=$HA_PUBLICATION_REQUIRED"
}

rollback_atomic_swap(){
  REASON=$1
  [ "$ATOMIC_SWAP_ACTIVE" -eq 1 ] || return 0
  [ -n "$ATOMIC_SWAP_RUNNER" ] && [ -f "$ATOMIC_SWAP_RUNNER" ] || return 1
  command -v python3 >/dev/null 2>&1 || return 1
  if python3 "$ATOMIC_SWAP_RUNNER" rollback \
      --root "$ROOT" \
      --from-version "$CURRENT_VERSION" \
      --to-version "$NEW_VERSION" \
      --reason "$REASON"; then
    ATOMIC_SWAP_ACTIVE=0
    log "Atomic rollback voltooid: $NEW_VERSION -> $CURRENT_VERSION"
    return 0
  fi
  return 1
}

fail(){
  MSG="$*"
  ROLLBACK_OK=1
  if [ "$ATOMIC_SWAP_ACTIVE" -eq 1 ]; then
    if ! rollback_atomic_swap "$MSG"; then
      ROLLBACK_OK=0
      log "FOUT: atomic rollback kon niet veilig worden afgerond; release-hold blijft actief"
    fi
  fi
  if [ "$RELEASE_HOLD_ARMED" -eq 1 ] && [ "$ROLLBACK_OK" -eq 1 ]; then
    restore_previous_release_validation_hold || log "FOUT: vorige release-hold kon niet worden hersteld"
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
TARGET_PM_VERSION="$(tr -d '\r\n ' < "$STAGE/slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt" 2>/dev/null || true)"
[ -n "$TARGET_PM_VERSION" ] || fail "target Projectmanager VERSION.txt ontbreekt of is leeg"
ARTIFACT_SHA256="$(sha256sum "$ZIP_WORK" 2>/dev/null | awk '{print $1}')"
[ -n "$ARTIFACT_SHA256" ] || fail "release artifact SHA256 kon niet worden bepaald"

log "FASE 3/8: huidige installatie controleren"
cd "$PROJECT"
CURRENT_VERSION="$(tr -d '\r\n ' < VERSIE.txt 2>/dev/null || true)"
CURRENT_PM_VERSION="$(tr -d '\r\n ' < "$PROJECT/slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt" 2>/dev/null || true)"
[ -n "$CURRENT_VERSION" ] || fail "huidige App-versie ontbreekt"
[ -n "$CURRENT_PM_VERSION" ] || fail "huidige Projectmanager-versie ontbreekt"
CURRENT_MANIFEST_SHA256="$(sha256sum "$PROJECT/MANIFEST.sha256" 2>/dev/null | awk '{print $1}')"
[ -n "$CURRENT_MANIFEST_SHA256" ] || fail "huidig MANIFEST.sha256 ontbreekt voor GitHub-publicatiecontract"
TARGET_MANIFEST_SHA256="$(sha256sum "$STAGE/MANIFEST.sha256" 2>/dev/null | awk '{print $1}')"
[ -n "$TARGET_MANIFEST_SHA256" ] || fail "release MANIFEST.sha256 ontbreekt voor GitHub-publicatiecontract"
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

# Atomic swap runner is copied to /tmp before App is renamed, so rollback never
# depends on a possibly broken newly-active worktree.
[ -f "$ATOMIC_SWAP" ] || fail "atomic swap helper ontbreekt: $ATOMIC_SWAP"
command -v python3 >/dev/null 2>&1 || fail "python3 ontbreekt voor atomic swap executor"
ATOMIC_SWAP_RUNNER="$(mktemp /tmp/energie-atomic-swap.XXXXXX.py)" || fail "atomic swap runner tempfile mislukt"
cp "$ATOMIC_SWAP" "$ATOMIC_SWAP_RUNNER" || fail "atomic swap helper naar /tmp kopieren mislukt"

log "FASE 4/8: volledige herstelbackup maken"
STAMP="$(date '+%Y%m%d-%H%M%S')"
BACKUP="$BACKUPS/EnergieProject_pre_${NEW_VERSION}_${STAMP}.tar.gz"
tar --exclude='./.git' -czf "$BACKUP" . || fail "backup maken mislukt"
tar -tzf "$BACKUP" >/dev/null 2>&1 || fail "backup-validatie mislukt"
chgrp everyone "$BACKUP" 2>/dev/null || true
chmod 660 "$BACKUP" || fail "pre-release backup groepsrechten instellen mislukt"
log "Backup gevalideerd: $BACKUP"

write_release_validation_hold || fail "release validation hold activeren mislukt"
log "FASE 5/8: atomic App prepare-and-swap"
if python3 "$ATOMIC_SWAP_RUNNER" prepare-and-swap \
    --root "$ROOT" \
    --artifact "$ZIP_WORK" \
    --expected-sha256 "$ARTIFACT_SHA256" \
    --from-version "$CURRENT_VERSION" \
    --from-pm-version "$CURRENT_PM_VERSION" \
    --to-version "$NEW_VERSION" \
    --to-pm-version "$TARGET_PM_VERSION" \
    --installer-context; then
  ATOMIC_SWAP_ACTIVE=1
else
  fail "atomic App prepare-and-swap mislukt"
fi
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
  log "Git-publicatie wordt na canonieke processed-archivering via het gevalideerde HA-publicatiecontract afgehandeld"
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
CANONICAL_PROCESSED="$PROCESSED/EnergieProject_v${NEW_VERSION}.zip"
rm -f "$CANONICAL_PROCESSED" || fail "oude canonieke processed release verwijderen mislukt"
mv "$ZIP_WORK" "$CANONICAL_PROCESSED" || fail "release naar processed verplaatsen mislukt"
ZIP_WORK="$CANONICAL_PROCESSED"
if [ "$GIT_AVAILABLE" -eq 0 ]; then
  PROCESSED_SHA256="$(sha256sum "$CANONICAL_PROCESSED" 2>/dev/null | awk '{print $1}')"
  [ -n "$PROCESSED_SHA256" ] || fail "processed release SHA256 kon niet worden bepaald"
  write_ha_publication_required "$PROCESSED_SHA256" || fail "HA-publicatiecontract schrijven mislukt"
fi
cleanup_old_backups
cleanup_processed_releases
# Laat atomic rollback actief tot ook de post-release acceptance-marker duurzaam staat.
write_post_release_maintenance_required || fail "post-release MAINTENANCE-marker schrijven mislukt"
ZIP_WORK=""
WORKTREE_REPLACED=0
ATOMIC_SWAP_ACTIVE=0
log "SUCCES: $CURRENT_VERSION -> $NEW_VERSION; $FINAL_DETAIL; ZIP canoniek gearchiveerd als EnergieProject_v${NEW_VERSION}.zip in processed."
schedule_watcher_refresh
