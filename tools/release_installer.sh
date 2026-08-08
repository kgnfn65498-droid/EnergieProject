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

log(){ printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
fail(){ log "FOUT: $*"; [ -n "${ZIP_WORK:-}" ] && [ -f "$ZIP_WORK" ] && mv "$ZIP_WORK" "$FAILED/" 2>/dev/null || true; rmdir "$LOCK" 2>/dev/null || true; exit 1; }

mkdir -p "$INCOMING" "$PROCESSING" "$PROCESSED" "$FAILED" "$BACKUPS"
mkdir "$LOCK" 2>/dev/null || fail "installer is al actief"
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT INT TERM

set -- "$INCOMING"/*.zip
[ -e "$1" ] || { log "Geen release-ZIP in incoming."; exit 0; }
[ "$#" -eq 1 ] || fail "verwacht exact één ZIP in incoming, gevonden: $#"
ZIP="$1"
ZIP_WORK="$PROCESSING/$(basename "$ZIP")"
mv "$ZIP" "$ZIP_WORK"
log "Release gevonden: $(basename "$ZIP_WORK")"

unzip -t "$ZIP_WORK" >/dev/null 2>&1 || fail "ZIP-integriteit ongeldig"
LIST="$(unzip -l "$ZIP_WORK" | awk '{print $4}')"
for f in $REQUIRED; do printf '%s\n' "$LIST" | grep -Fxq "$f" || fail "verplicht bestand ontbreekt: $f"; done

STAGE="$(mktemp -d /tmp/energie-release.XXXXXX)"
trap 'rm -rf "$STAGE"; rmdir "$LOCK" 2>/dev/null || true' EXIT INT TERM
unzip -q "$ZIP_WORK" -d "$STAGE" || fail "uitpakken naar staging mislukt"
(cd "$STAGE" && sha256sum -c MANIFEST.sha256 >/dev/null) || fail "SHA256-validatie mislukt"
NEW_VERSION="$(tr -d '\r\n ' < "$STAGE/VERSIE.txt")"
[ -n "$NEW_VERSION" ] || fail "VERSIE.txt is leeg"

cd "$PROJECT"
git diff --quiet && git diff --cached --quiet || fail "project bevat lokale wijzigingen"
BASE_COMMIT="$(git rev-parse HEAD)"
CURRENT_VERSION="$(tr -d '\r\n ' < VERSIE.txt 2>/dev/null || true)"
STAMP="$(date '+%Y%m%d-%H%M%S')"
BACKUP="$BACKUPS/EnergieProject_pre_${NEW_VERSION}_${STAMP}.tar.gz"
tar --exclude='./.git' -czf "$BACKUP" . || fail "backup maken mislukt"
log "Backup: $BACKUP"

# Vervang uitsluitend de release-worktree; .git blijft behouden.
find "$PROJECT" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} + || fail "oude worktree leegmaken mislukt"
cp -a "$STAGE"/. "$PROJECT"/ || fail "nieuwe release kopiëren mislukt"

git config core.filemode false
if [ -f tests/test_static.py ]; then
  if command -v python3 >/dev/null 2>&1; then python3 -m pytest -q tests/test_static.py || { git reset --hard "$BASE_COMMIT"; fail "statische tests mislukt; rollback uitgevoerd"; }; fi
fi

git add -A
if git diff --cached --quiet; then
  log "Geen inhoudelijke wijziging; release $NEW_VERSION is al actief."
else
  git commit -m "v${NEW_VERSION}: automated release inbox install" || { git reset --hard "$BASE_COMMIT"; fail "commit mislukt; rollback uitgevoerd"; }
  git push origin main || { git reset --hard "$BASE_COMMIT"; fail "push mislukt; lokale rollback uitgevoerd"; }
fi
mv "$ZIP_WORK" "$PROCESSED/"
ZIP_WORK=""
log "SUCCES: $CURRENT_VERSION -> $NEW_VERSION; ZIP gearchiveerd in processed."
