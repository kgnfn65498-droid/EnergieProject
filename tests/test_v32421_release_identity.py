from release_test_contract import CURRENT_PM_VERSION, CURRENT_RELEASE


def _release_tuple(value):
    return tuple(int(part) for part in str(value).split('.'))


def _pm_rc(value):
    return int(str(value).rsplit('rc', 1)[1])


def test_v32421_release_identity_contract_remains_valid_for_successors():
    assert _release_tuple(CURRENT_RELEASE) >= (32, 4, 21)
    assert _pm_rc(CURRENT_PM_VERSION) >= 18
