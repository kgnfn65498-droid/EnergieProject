import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "tools/release_installer.sh"


def _text() -> str:
    return INSTALLER.read_text(encoding="utf-8")


def test_hold_is_armed_before_git_publication_and_ha_publication():
    text = _text()
    hold_call = 'write_release_validation_hold || fail "release validation hold activeren mislukt"'
    git_push = "git push origin main"
    ha_publish = 'write_ha_publication_required "$PROCESSED_SHA256"'
    assert text.count(hold_call) == 1
    assert git_push in text
    assert ha_publish in text
    assert text.index(hold_call) < text.index(git_push)
    assert text.index(hold_call) < text.index(ha_publish)


def test_failed_release_restores_previous_hold_state():
    text = _text()
    assert "capture_previous_release_validation_hold(){" in text
    assert "restore_previous_release_validation_hold(){" in text
    fail_block = text.split("fail(){", 1)[1].split("\n}", 1)[0]
    assert 'restore_previous_release_validation_hold || log "FOUT: vorige release-hold kon niet worden hersteld"' in fail_block


def test_successful_release_keeps_new_hold_marker():
    text = _text()
    success_tail = text.split('log "SUCCES:', 1)[1]
    assert "restore_previous_release_validation_hold" not in success_tail
