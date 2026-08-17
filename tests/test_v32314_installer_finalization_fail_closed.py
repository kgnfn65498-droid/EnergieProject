from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "tools/release_installer.sh"


def text():
    return INSTALLER.read_text(encoding="utf-8")


def test_ha_publication_marker_is_read_back_as_regular_file():
    t = text()
    fn = t.split("write_ha_publication_required(){", 1)[1].split("\n}", 1)[0]
    assert '[ -d "$HA_PUBLICATION_REQUIRED" ] && return 1' in fn
    assert 'mv "$TMP_PUBLICATION" "$HA_PUBLICATION_REQUIRED" ||' in fn
    assert '[ -f "$HA_PUBLICATION_REQUIRED" ] || return 1' in fn
    assert 'grep -Fq "\\\"version\\\":\\\"$NEW_VERSION\\\"" "$HA_PUBLICATION_REQUIRED" || return 1' in fn


def test_phase8_publication_failure_uses_fail_path_and_remains_rollbackable():
    t = text()
    phase8 = t.split('log "FASE 8/8: eindcontrole en archivering"', 1)[1]
    publication = 'write_ha_publication_required "$PROCESSED_SHA256" || fail "HA-publicatiecontract schrijven mislukt"'
    assert publication in phase8
    assert 'ZIP_WORK="$CANONICAL_PROCESSED"' in phase8
    assert phase8.index('ZIP_WORK="$CANONICAL_PROCESSED"') < phase8.index(publication)
    assert phase8.index(publication) < phase8.index('WORKTREE_REPLACED=0')
    assert phase8.index(publication) < phase8.index('ZIP_WORK=""')


def test_processed_move_is_fail_closed():
    t = text()
    phase8 = t.split('log "FASE 8/8: eindcontrole en archivering"', 1)[1]
    assert 'rm -f "$CANONICAL_PROCESSED" || fail "oude canonieke processed release verwijderen mislukt"' in phase8
    assert 'mv "$ZIP_WORK" "$CANONICAL_PROCESSED" || fail "release naar processed verplaatsen mislukt"' in phase8
