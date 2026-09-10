#!/bin/sh
set -eu

ROOT=${1:-}
[ -n "$ROOT" ] || { echo "FOUT: projectroot ontbreekt" >&2; exit 2; }
CLEARUP="$ROOT/CLEARUP"

if [ -L "$CLEARUP" ]; then
  echo "FOUT: CLEARUP-root mag geen symlink zijn: $CLEARUP" >&2
  exit 1
fi
if [ -e "$CLEARUP" ] && [ ! -d "$CLEARUP" ]; then
  echo "FOUT: CLEARUP-root bestaat maar is geen directory: $CLEARUP" >&2
  exit 1
fi
if [ ! -d "$CLEARUP" ]; then
  mkdir "$CLEARUP" || { echo "FOUT: CLEARUP-root kon niet worden aangemaakt: $CLEARUP" >&2; exit 1; }
fi
# Match the proven runtime-writable project surface while using the sticky bit
# so unrelated local users cannot remove each other's top-level entries.
chmod 1777 "$CLEARUP" || { echo "FOUT: CLEARUP-root kon niet schrijfbaar worden gemaakt: $CLEARUP" >&2; exit 1; }
[ -d "$CLEARUP" ] && [ ! -L "$CLEARUP" ] || { echo "FOUT: ongeldige CLEARUP-root na bootstrap" >&2; exit 1; }
PROBE="$CLEARUP/.clearup-write-probe.$$"
( umask 077; : > "$PROBE" ) || { echo "FOUT: CLEARUP-root write-probe mislukt" >&2; exit 1; }
rm -f "$PROBE" || { echo "FOUT: CLEARUP-root probe kon niet worden verwijderd" >&2; exit 1; }
printf 'CLEARUP_ROOT_READY %s
' "$CLEARUP"
