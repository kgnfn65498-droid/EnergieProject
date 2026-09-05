#!/bin/sh
set -eu
umask 077

if [ -n "${ENERGIE_ROOT:-}" ]; then
  ROOT="$ENERGIE_ROOT"
elif [ -d "/share/CACHEDEV1_DATA/AI Projecten/EnergieProject/Inbox" ]; then
  ROOT="/share/CACHEDEV1_DATA/AI Projecten/EnergieProject"
elif [ -d "/share/AI Projecten/EnergieProject/Inbox" ]; then
  ROOT="/share/AI Projecten/EnergieProject"
elif [ -d "/share/Energie_NAS/EnergieProject/Inbox" ]; then
  ROOT="/share/Energie_NAS/EnergieProject"
else
  echo "FOUT: EnergieProject-root niet gevonden" >&2
  exit 1
fi

SYSTEM="$ROOT/Data/03_Systeem"
PUBLISHER="$ROOT/App/tools/nas_github_publisher.sh"
PRIVATE="$SYSTEM/Projectmanager/Private/github_publisher"
PUBLIC_KEY="$PRIVATE/id_ed25519.pub"
KNOWN_HOSTS="$PRIVATE/known_hosts"
CONTAINER_NAME="energie-github-publisher"
RUNTIME_TAG="alpine/git:2.54.0"
OFFICIAL_GITHUB_ED25519="github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl"

DOCKER="$(command -v docker 2>/dev/null || true)"
if [ -z "$DOCKER" ]; then
  for candidate in "/share/CACHEDEV1_DATA/.qpkg/container-station/bin/docker" "/share/CACHEDEV2_DATA/.qpkg/container-station/bin/docker" "/usr/local/bin/docker"; do
    if [ -x "$candidate" ]; then DOCKER="$candidate"; break; fi
  done
fi
[ -n "$DOCKER" ] || { echo "FOUT: Docker/Container Station CLI niet gevonden" >&2; exit 2; }
[ -f "$PUBLISHER" ] || { echo "FOUT: nas_github_publisher.sh ontbreekt" >&2; exit 2; }
[ -d "$PRIVATE" ] || { echo "FOUT: private publishermap ontbreekt" >&2; exit 2; }
[ -f "$KNOWN_HOSTS" ] || { echo "FOUT: vooraf gepinde GitHub known_hosts ontbreekt" >&2; exit 2; }
grep -Fqx "$OFFICIAL_GITHUB_ED25519" "$KNOWN_HOSTS" || { echo "FOUT: GitHub Ed25519 host key wijkt af" >&2; exit 2; }

DOCKER_CLIENT_HOME="/tmp/energie-docker-client-$(id -u)"
mkdir -p "$DOCKER_CLIENT_HOME/.docker"
export HOME="$DOCKER_CLIENT_HOME"
export DOCKER_CONFIG="$DOCKER_CLIENT_HOME/.docker"
export XDG_CONFIG_HOME="$DOCKER_CLIENT_HOME/.config"

"$DOCKER" version >/dev/null 2>&1 || { echo "FOUT: Docker daemon niet bereikbaar" >&2; exit 3; }
RUNTIME_IMAGE="$RUNTIME_TAG"
if ! "$DOCKER" image inspect "$RUNTIME_IMAGE" >/dev/null 2>&1; then
  LEGACY_IMAGE_ID="$("$DOCKER" inspect -f '{{.Image}}' energie-git 2>/dev/null || true)"
  [ -n "$LEGACY_IMAGE_ID" ] || { echo "FOUT: bewezen lokale alpine/git runtime ontbreekt" >&2; exit 3; }
  "$DOCKER" image inspect "$LEGACY_IMAGE_ID" >/dev/null 2>&1 || { echo "FOUT: legacy energie-git image-id niet bruikbaar" >&2; exit 3; }
  RUNTIME_IMAGE="$LEGACY_IMAGE_ID"
fi

"$DOCKER" run --rm --entrypoint /bin/sh "$RUNTIME_IMAGE" -ec '
  set -eu
  for tool in git ssh ssh-keygen unzip sha256sum sed awk stat date tr grep mktemp; do
    command -v "$tool" >/dev/null || { echo "MISSING=$tool" >&2; exit 9; }
  done
'
echo PUBLISHER_RUNTIME_EXEC_GREEN

CONTRACT_SHA_BEFORE=""
if [ -f "$ROOT/Inbox/ha_publication_required.json" ]; then
  CONTRACT_SHA_BEFORE="$(sha256sum "$ROOT/Inbox/ha_publication_required.json" | awk '{print $1}')"
fi
"$DOCKER" run --rm --entrypoint /bin/sh -v "$PRIVATE:/publisher-private:rw" -v "$ROOT/Inbox:/energy/Inbox:rw" "$RUNTIME_IMAGE" -ec '
  set -eu
  printf probe > /publisher-private/.rw-probe; rm -f /publisher-private/.rw-probe
  printf probe > /energy/Inbox/.publisher-rw-probe; rm -f /energy/Inbox/.publisher-rw-probe
'
if [ -n "$CONTRACT_SHA_BEFORE" ]; then
  [ "$(sha256sum "$ROOT/Inbox/ha_publication_required.json" | awk '{print $1}')" = "$CONTRACT_SHA_BEFORE" ] || { echo "FOUT: contract wijzigde tijdens preflight" >&2; exit 4; }
fi
echo PUBLISHER_BIND_MOUNTS_GREEN

"$DOCKER" run --rm --entrypoint /bin/sh -v "$PRIVATE:/publisher-private:rw" "$RUNTIME_IMAGE" -ec '
  set -eu
  chmod 700 /publisher-private
  if [ ! -f /publisher-private/id_ed25519 ]; then
    ssh-keygen -q -t ed25519 -N "" -C "EnergieProject autonomous NAS publisher" -f /publisher-private/id_ed25519
  fi
  chmod 600 /publisher-private/id_ed25519
  chmod 644 /publisher-private/id_ed25519.pub
  chmod 600 /publisher-private/known_hosts
  ssh-keygen -lf /publisher-private/id_ed25519.pub >/dev/null
'
[ -s "$PUBLIC_KEY" ] || { echo "FOUT: public deploy key ontbreekt" >&2; exit 5; }
echo PUBLISHER_DEPLOY_KEY_READY

"$DOCKER" rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
"$DOCKER" run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  --entrypoint /bin/sh \
  -e ENERGIE_ROOT=/energy \
  -e ENERGIE_PUBLISHER_PRIVATE_ROOT=/publisher-private \
  -v "$ROOT/Inbox:/energy/Inbox:rw" \
  -v "$PRIVATE:/publisher-private:rw" \
  -v "$PUBLISHER:/usr/local/bin/nas_github_publisher.sh:ro" \
  "$RUNTIME_IMAGE" \
  -ec 'while :; do if [ -f /publisher-private/enabled ]; then sh /usr/local/bin/nas_github_publisher.sh || true; fi; sleep 15; done' >/dev/null
sleep 2
"$DOCKER" ps --filter "name=^/${CONTAINER_NAME}$" --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME" || { "$DOCKER" logs "$CONTAINER_NAME" 2>&1 | tail -n 30 >&2 || true; echo "FOUT: publishercontainer draait niet" >&2; exit 6; }
[ ! -e "$PRIVATE/enabled" ] || { echo "FOUT: publisher stond onverwacht al enabled" >&2; exit 6; }
if [ -n "$CONTRACT_SHA_BEFORE" ]; then
  [ "$(sha256sum "$ROOT/Inbox/ha_publication_required.json" | awk '{print $1}')" = "$CONTRACT_SHA_BEFORE" ] || { echo "FOUT: contract wijzigde tijdens bootstrap" >&2; exit 6; }
fi

echo PUBLISHER_WAITING_GREEN
printf '%s\n' "PUBLISHER_DEPLOY_KEY_PUBLIC=$(cat "$PUBLIC_KEY")"
printf '%s\n' 'PUBLICATION_ENABLED=NO'
printf '%s\n' 'PRODUCTION_RELEASE_MODIFIED=NO'
