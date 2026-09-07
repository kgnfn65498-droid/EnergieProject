#!/bin/sh
set -eu

ROOT="${ENERGIE_ROOT:-/energy}"
CONTRACT="$ROOT/Inbox/ha_publication_required.json"
PROCESSED="$ROOT/Inbox/processed"
STATE="$ROOT/Inbox/github_publisher_state.json"
HISTORY="$ROOT/Inbox/github_publisher_history.jsonl"
PRIVATE_ROOT="${ENERGIE_PUBLISHER_PRIVATE_ROOT:-/publisher-private}"
KEY="$PRIVATE_ROOT/id_ed25519"
KNOWN_HOSTS="$PRIVATE_ROOT/known_hosts"
LOCK="$ROOT/Inbox/.github_publisher.lock"
TMP_ROOT=""
VERSION=""
MODE="${ENERGIE_PUBLISHER_MODE:-publish}"

json_escape() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
archive_previous_state() {
  [ -s "$STATE" ] || return 0
  PREVIOUS_STATE="$(tr -d '\r\n' < "$STATE")"
  case "$PREVIOUS_STATE" in
    \{*\}) printf '%s\n' "$PREVIOUS_STATE" >> "$HISTORY" ;;
    *) return 0 ;;
  esac
}
write_state() { STATUS="$1"; MESSAGE="$2"; VERSION_VALUE="${3:-}"; TMP_STATE="$STATE.tmp.$$"; NOW="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"; printf '{"schema_version":1,"status":"%s","version":"%s","message":"%s","updated_at":"%s"}\n' "$(json_escape "$STATUS")" "$(json_escape "$VERSION_VALUE")" "$(json_escape "$MESSAGE")" "$NOW" > "$TMP_STATE"; archive_previous_state; mv "$TMP_STATE" "$STATE"; }
fail() { MSG="$1"; VERSION_VALUE="${2:-$VERSION}"; write_state "error" "$MSG" "$VERSION_VALUE" || true; printf '%s\n' "PUBLISHER_ERROR=$MSG" >&2; exit 1; }
cleanup() { [ -n "$TMP_ROOT" ] && rm -rf "$TMP_ROOT" 2>/dev/null || true; rmdir "$LOCK" 2>/dev/null || true; }
trap 'cleanup' EXIT INT TERM
mkdir -p "$ROOT/Inbox" "$PROCESSED"; mkdir "$LOCK" 2>/dev/null || exit 0
if [ ! -f "$CONTRACT" ]; then write_state "idle" "no publication contract" ""; exit 0; fi
case "$MODE" in publish|probe) ;; *) fail "invalid publisher mode: $MODE" "" ;; esac
json_string_field() { FIELD="$1"; VALUE="$(sed -n 's/.*"'"$FIELD"'"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$CONTRACT" | head -n 1)"; [ -n "$VALUE" ] || return 2; case "$VALUE" in *\\*) return 3 ;; esac; printf '%s' "$VALUE"; }
VERSION="$(json_string_field version)" || fail "contract missing/unsafe version" ""
REPOSITORY="$(json_string_field repository)" || fail "contract missing/unsafe repository"
BRANCH="$(json_string_field branch)" || fail "contract missing/unsafe branch"
ZIP_NAME="$(json_string_field processed_zip)" || fail "contract missing/unsafe processed_zip"
ZIP_SHA_EXPECTED="$(json_string_field processed_zip_sha256)" || fail "contract missing/unsafe processed_zip_sha256"
EXPECTED_PREVIOUS_VERSION="$(json_string_field expected_previous_version)" || fail "contract missing/unsafe expected_previous_version"
EXPECTED_PREVIOUS_MANIFEST_SHA256="$(json_string_field expected_previous_manifest_sha256)" || fail "contract missing/unsafe expected_previous_manifest_sha256"
TARGET_MANIFEST_SHA256="$(json_string_field target_manifest_sha256)" || fail "contract missing/unsafe target_manifest_sha256"
case "$VERSION:$EXPECTED_PREVIOUS_VERSION" in *[!0-9A-Za-z._:-]*) fail "contract version fields unsafe" ;; esac
case "$ZIP_NAME" in */*|*\\*|*..*|*[!A-Za-z0-9._-]*) fail "unsafe processed_zip path" ;; esac
case "$BRANCH" in ""|/*|*/|*..*|*//*|*[!A-Za-z0-9._/-]*) fail "unsafe branch" ;; esac
case "$REPOSITORY" in "https://github.com/kgnfn65498-droid/EnergieProject"|"https://github.com/kgnfn65498-droid/EnergieProject.git"|"git@github.com:kgnfn65498-droid/EnergieProject.git") ;; *) fail "repository not allowlisted" ;; esac
for SHA_VALUE in "$ZIP_SHA_EXPECTED" "$EXPECTED_PREVIOUS_MANIFEST_SHA256" "$TARGET_MANIFEST_SHA256"; do [ "${#SHA_VALUE}" -eq 64 ] || fail "contract SHA256 length invalid"; case "$SHA_VALUE" in *[!0-9a-fA-F]*) fail "contract SHA256 invalid" ;; esac; done
ZIP_PATH="$PROCESSED/$ZIP_NAME"; [ -f "$ZIP_PATH" ] || fail "processed ZIP missing"; ZIP_SHA_ACTUAL="$(sha256sum "$ZIP_PATH" | awk '{print $1}')"; [ "$ZIP_SHA_ACTUAL" = "$ZIP_SHA_EXPECTED" ] || fail "processed ZIP SHA256 mismatch"
[ -f "$KEY" ] || fail "dedicated deploy key missing"; KEY_MODE="$(stat -c '%a' "$KEY" 2>/dev/null || true)"; case "$KEY_MODE" in 600|400) ;; *) fail "deploy key permissions are not private" ;; esac
[ -f "$KNOWN_HOSTS" ] || fail "known_hosts missing"; grep -Fq 'github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl' "$KNOWN_HOSTS" || fail "official GitHub Ed25519 host key not pinned"
REPO_SSH="git@github.com:kgnfn65498-droid/EnergieProject.git"; export GIT_SSH_COMMAND="ssh -i $KEY -o IdentitiesOnly=yes -o UserKnownHostsFile=$KNOWN_HOSTS -o StrictHostKeyChecking=yes -o BatchMode=yes"
TMP_ROOT="$(mktemp -d /tmp/energie-publisher.XXXXXX)"; SRC="$TMP_ROOT/source"; WORK="$TMP_ROOT/work"; VERIFY="$TMP_ROOT/verify"; NAMES="$TMP_ROOT/zip_names.txt"; mkdir -p "$SRC"
unzip -t "$ZIP_PATH" >/dev/null || fail "processed ZIP integrity failed"; unzip -l "$ZIP_PATH" | awk 'NR>3 { if ($1 ~ /^-+$/) exit; if (NF >= 4) print $4 }' > "$NAMES" || fail "cannot list processed ZIP"; [ -s "$NAMES" ] || fail "processed ZIP file list empty"; while IFS= read -r NAME; do case "$NAME" in /*|../*|*/../*|*\\*) fail "unsafe ZIP member path" ;; esac; done < "$NAMES"; unzip -q "$ZIP_PATH" -d "$SRC" || fail "cannot extract processed ZIP"
[ -f "$SRC/MANIFEST.sha256" ] || fail "target MANIFEST.sha256 missing"; [ -f "$SRC/VERSIE.txt" ] || fail "target VERSIE.txt missing"; TARGET_MANIFEST_ACTUAL="$(sha256sum "$SRC/MANIFEST.sha256" | awk '{print $1}')"; [ "$TARGET_MANIFEST_ACTUAL" = "$TARGET_MANIFEST_SHA256" ] || fail "target manifest SHA mismatch"; (cd "$SRC" && sha256sum -c MANIFEST.sha256 >/dev/null) || fail "target manifest file validation failed"; [ "$(tr -d '\r\n ' < "$SRC/VERSIE.txt")" = "$VERSION" ] || fail "target VERSIE.txt mismatch"
CONTRACT_SHA_BEFORE="$(sha256sum "$CONTRACT" | awk '{print $1}')"; REMOTE_HEAD="$(git ls-remote "$REPO_SSH" "refs/heads/$BRANCH" | awk 'NR==1{print $1}')"; [ -n "$REMOTE_HEAD" ] || fail "remote branch not found"; git clone --quiet --depth 1 --branch "$BRANCH" "$REPO_SSH" "$WORK" || fail "remote clone failed"; [ -f "$WORK/VERSIE.txt" ] || fail "remote VERSIE.txt missing"; [ -f "$WORK/MANIFEST.sha256" ] || fail "remote MANIFEST.sha256 missing"; REMOTE_VERSION="$(tr -d '\r\n ' < "$WORK/VERSIE.txt")"; REMOTE_MANIFEST_SHA256="$(sha256sum "$WORK/MANIFEST.sha256" | awk '{print $1}')"
historical_zip_sha() {
  case "$1" in
    32.4.0) printf '%s' 'a4bd8c377ae67a6db35374b9ffcf07853964018727e79e5d15973b697ca2dfcd' ;;
    32.4.1) printf '%s' '94c101e70f5f442823f0783e559cb3b5ab6491ddb21097afec51568d96d5c3e6' ;;
    32.4.2) printf '%s' '0a04d365aa7428c83d4d27091307c6b262f167367a05bfb1ed6afbeaeeebf74c' ;;
    32.4.3) printf '%s' '70a3d3cc4cac1930406302d85771abdcf0b950f978a0983c32da129fc5bff1f1' ;;
    32.4.4) printf '%s' '772fcb589e646afa38fc367c74b1ea79c43f53844bb97c142d93041e52d2350b' ;;
    32.4.5) printf '%s' '15b2c06f927c05c191be5a008240e820825101ccabdbd6f2ada8412729c51244' ;;
    *) return 1 ;;
  esac
}

validate_historical_baseline() {
  HIST_EXPECTED_ZIP_SHA="$(historical_zip_sha "$REMOTE_VERSION")" || return 1
  HIST_ZIP="$PROCESSED/EnergieProject_v${REMOTE_VERSION}.zip"
  [ -f "$HIST_ZIP" ] || return 1
  HIST_ACTUAL_ZIP_SHA="$(sha256sum "$HIST_ZIP" | awk '{print $1}')"
  [ "$HIST_ACTUAL_ZIP_SHA" = "$HIST_EXPECTED_ZIP_SHA" ] || return 1
  HIST_DIR="$TMP_ROOT/historical-${REMOTE_VERSION}"
  mkdir -p "$HIST_DIR"
  unzip -t "$HIST_ZIP" >/dev/null || return 1
  unzip -q "$HIST_ZIP" -d "$HIST_DIR" || return 1
  [ -f "$HIST_DIR/VERSIE.txt" ] || return 1
  [ -f "$HIST_DIR/MANIFEST.sha256" ] || return 1
  [ "$(tr -d '\r\n ' < "$HIST_DIR/VERSIE.txt")" = "$REMOTE_VERSION" ] || return 1
  HIST_MANIFEST_SHA256="$(sha256sum "$HIST_DIR/MANIFEST.sha256" | awk '{print $1}')"
  [ "$HIST_MANIFEST_SHA256" = "$REMOTE_MANIFEST_SHA256" ] || return 1
  (cd "$HIST_DIR" && sha256sum -c MANIFEST.sha256 >/dev/null) || return 1
  (cd "$WORK" && sha256sum -c MANIFEST.sha256 >/dev/null) || return 1
  return 0
}

if [ "$REMOTE_VERSION" = "$VERSION" ] && [ "$REMOTE_MANIFEST_SHA256" = "$TARGET_MANIFEST_SHA256" ]; then
  (cd "$WORK" && sha256sum -c MANIFEST.sha256 >/dev/null) || fail "target_exact remote manifest validation failed"
  if [ "$MODE" = probe ]; then
    write_state "ready" "probe ready: remote=$REMOTE_VERSION classification=target_exact" "$VERSION"
    printf '%s\n' "PUBLISHER_PROBE_GREEN=target_exact:$REMOTE_VERSION"
    exit 0
  fi
  CURRENT_CONTRACT_SHA="$(sha256sum "$CONTRACT" | awk '{print $1}')"
  [ "$CURRENT_CONTRACT_SHA" = "$CONTRACT_SHA_BEFORE" ] || fail "publication contract changed during verification"
  rm -f "$CONTRACT"
  write_state "published" "target already exact on GitHub" "$VERSION"
  printf '%s\n' "PUBLISHER_TARGET_EXACT_OK=$VERSION"
  exit 0
fi

BASELINE_CLASSIFICATION=""
if [ "$REMOTE_VERSION" = "$EXPECTED_PREVIOUS_VERSION" ] && [ "$REMOTE_MANIFEST_SHA256" = "$EXPECTED_PREVIOUS_MANIFEST_SHA256" ]; then
  (cd "$WORK" && sha256sum -c MANIFEST.sha256 >/dev/null) || fail "previous remote manifest validation failed"
  BASELINE_CLASSIFICATION="expected_previous"
elif validate_historical_baseline; then
  BASELINE_CLASSIFICATION="validated_historical_previous"
else
  fail "remote baseline mismatch: version=$REMOTE_VERSION manifest=$REMOTE_MANIFEST_SHA256"
fi

if [ "$MODE" = probe ]; then
  write_state "ready" "probe ready: remote=$REMOTE_VERSION classification=$BASELINE_CLASSIFICATION" "$VERSION"
  printf '%s\n' "PUBLISHER_PROBE_GREEN=$BASELINE_CLASSIFICATION:$REMOTE_VERSION"
  exit 0
fi
for ITEM in "$WORK"/* "$WORK"/.[!.]* "$WORK"/..?*; do [ -e "$ITEM" ] || continue; [ "$(basename "$ITEM")" = ".git" ] && continue; rm -rf "$ITEM"; done
cp -R "$SRC"/. "$WORK"/
(cd "$WORK"; git config user.name "EnergieProject autonomous NAS publisher"; git config user.email "energieproject-publisher@localhost"; git add -A; git diff --cached --quiet && exit 3; git commit -m "v${VERSION}: autonomous NAS publication" >/dev/null) || fail "validated release could not be committed"
LOCAL_FINAL="$(cd "$WORK" && git rev-parse HEAD)"; (cd "$WORK" && git push origin "HEAD:$BRANCH") || fail "GitHub push failed"
REMOTE_FINAL="$(git ls-remote "$REPO_SSH" "refs/heads/$BRANCH" | awk 'NR==1{print $1}')"; [ "$REMOTE_FINAL" = "$LOCAL_FINAL" ] || fail "remote HEAD does not equal published commit"; git clone --quiet --depth 1 --branch "$BRANCH" "$REPO_SSH" "$VERIFY" || fail "post-push verification clone failed"; [ "$(tr -d '\r\n ' < "$VERIFY/VERSIE.txt")" = "$VERSION" ] || fail "post-push version mismatch"; VERIFY_MANIFEST_SHA256="$(sha256sum "$VERIFY/MANIFEST.sha256" | awk '{print $1}')"; [ "$VERIFY_MANIFEST_SHA256" = "$TARGET_MANIFEST_SHA256" ] || fail "post-push manifest SHA mismatch"; (cd "$VERIFY" && sha256sum -c MANIFEST.sha256 >/dev/null) || fail "post-push manifest file validation failed"
CURRENT_CONTRACT_SHA="$(sha256sum "$CONTRACT" | awk '{print $1}')"; [ "$CURRENT_CONTRACT_SHA" = "$CONTRACT_SHA_BEFORE" ] || fail "publication contract changed before cleanup"; rm -f "$CONTRACT"; write_state "published" "validated release published and remotely verified" "$VERSION"; printf '%s\n' "PUBLISHER_PUBLISHED_OK=$VERSION"
