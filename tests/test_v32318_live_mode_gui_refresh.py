import pathlib
import sys

APP_ROOT = pathlib.Path(__file__).resolve().parents[1] / "slimmemeterportal_import/rootfs/app"
sys.path.insert(0, str(APP_ROOT))

import operating_mode_web as web


def _snapshot():
    return {
        "base_mode": "DEVELOPMENT",
        "effective_mode": "DEVELOPMENT",
        "automatic_switching_enabled": True,
        "development_session_active": True,
        "temporary_reason": "",
        "reconciliation_status": "ok",
        "drift": [],
        "desired_profile": {
            "release_ingress_enabled": True,
            "automatic_month_close_enabled": True,
        },
        "observed_profile": {"automatic_month_close_effective": False},
        "release_validation_hold": {
            "active": True,
            "validation_status": "required",
            "reconcile_status": "required",
        },
    }


def test_mode_card_intercepts_only_its_gui_forms_and_navigates_to_fresh_redirect():
    card = web.render_mode_card(_snapshot())
    assert 'const modeCard = document.getElementById("operating-mode-card")' in card
    assert 'modeCard.querySelectorAll("form")' in card
    assert 'input[name="return_ui"][value="1"]' in card
    assert 'form.addEventListener("submit", async (event)' in card
    assert "event.preventDefault()" in card
    assert "new FormData(form)" in card
    assert 'credentials: "same-origin"' in card
    assert 'cache: "no-store"' in card
    assert 'redirect: "follow"' in card
    assert "window.location.replace(response.url)" in card
    assert "window.location.reload()" in card
    assert "document.querySelectorAll(\"form\")" not in card


def test_release_hold_notice_classification_is_truthful():
    assert web._notice_result("validate-release-hold", {}, {"status": "released"}) == (
        "release_hold_released",
        "success",
    )
    assert web._notice_result("validate-release-hold", {}, {"status": "already_released"}) == (
        "release_hold_already_released",
        "success",
    )
    assert web._notice_result("validate-release-hold", {}, {"status": "blocked"}) == (
        "release_hold_blocked",
        "error",
    )


def test_emergency_hold_notice_classification_is_truthful():
    assert web._notice_result("emergency-release-hold", {}, {"status": "released_emergency"}) == (
        "emergency_release_done",
        "success",
    )
    assert web._notice_result("emergency-release-hold", {}, {"status": "already_released"}) == (
        "release_hold_already_released",
        "success",
    )
    assert web._notice_result("emergency-release-hold", {}, {"status": "confirmation_required"}) == (
        "emergency_confirmation_required",
        "error",
    )
    assert web._notice_result("emergency-release-hold", {}, {"status": "blocked"}) == (
        "emergency_release_blocked",
        "error",
    )


def test_fixed_notice_messages_include_blocked_and_already_released_states():
    card = web.render_mode_card(_snapshot())
    assert "release_hold_already_released" in card
    assert "Release-hold was al vrijgegeven" in card
    assert "release_hold_blocked" in card
    assert "Release-hold kon niet veilig worden vrijgegeven" in card
    assert "emergency_confirmation_required" in card
    assert "Noodvrijgave vereist bevestiging" in card
    assert "emergency_release_blocked" in card
    assert "Noodvrijgave is door veiligheidscontroles geblokkeerd" in card
