from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_previous_3249_conversation_intake_fixture_remains_historical():
    source = (ROOT / 'tests/test_v3249_conversation_intake.py').read_text(encoding='utf-8')
    assert "'32.4.9 Conversation Intake Bridge'" in source
    assert "'32.4.10 Conversation Intake Bridge'" not in source


def test_previous_3249_test_still_checks_current_candidate_identity_separately():
    source = (ROOT / 'tests/test_v3249_conversation_intake.py').read_text(encoding='utf-8')
    assert "== '32.4.10'" in source
    assert "'version: \"32.4.10\"'" in source
    assert "'APP_VERSION = \"32.4.10\"'" in source
    assert "'TARGET_RELEASE_VERSION = \"32.4.10\"'" in source
    assert "== '2.0.0-rc7'" in source


if __name__ == '__main__':
    test_previous_3249_conversation_intake_fixture_remains_historical()
    test_previous_3249_test_still_checks_current_candidate_identity_separately()
    print('V32410_RELEASE_SYNC_GUARD_GREEN')
