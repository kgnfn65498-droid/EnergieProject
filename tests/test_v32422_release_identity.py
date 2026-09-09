from release_test_contract import CURRENT_PM_VERSION, CURRENT_RELEASE


def test_v32422_release_identity():
    assert CURRENT_RELEASE == "32.4.22"
    assert CURRENT_PM_VERSION == "2.0.0-rc19"
