import io
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
        "observed_profile": {
            "automatic_month_close_effective": False,
        },
        "release_validation_hold": {
            "active": True,
            "validation_status": "required",
            "reconcile_status": "required",
        },
    }


def test_gui_success_redirects_ingress_relative():
    location = web._ui_redirect_location("development_set", "success")
    assert location.startswith("./?")
    assert "mode_notice=development_set" in location
    assert "mode_level=success" in location
    assert not location.startswith(("http://", "https://", "/"))


def test_gui_forms_opt_in_without_changing_api_callers():
    card = web.render_mode_card(_snapshot())
    assert card.count('name="return_ui" value="1"') >= 7


def test_non_gui_post_keeps_json_response(tmp_path):
    class Handler:
        def do_POST(self):
            self.delegated = True

    class App:
        pass

    App.Handler = Handler
    App.html_page = staticmethod(lambda ingress_path="": b"<html><body>basis</body></html>")
    web.install_mode_web(App, tmp_path)

    handler = Handler()
    payload = b"mode=DEVELOPMENT"
    handler.path = "/set-operating-mode"
    handler.headers = {"Content-Length": str(len(payload))}
    handler.rfile = io.BytesIO(payload)
    handler.send_body = lambda status, body, content_type: setattr(handler, "response", (status, body, content_type))
    handler.do_POST()
    assert handler.response[0] == 200
    assert handler.response[2] == "application/json; charset=utf-8"


def test_gui_post_returns_303_not_json(tmp_path):
    class Handler:
        def do_POST(self):
            self.delegated = True

        def send_response(self, status):
            self.redirect_status = status

        def send_header(self, name, value):
            self.response_headers = getattr(self, "response_headers", []) + [(name, value)]

        def end_headers(self):
            self.headers_ended = True

    class App:
        pass

    App.Handler = Handler
    App.html_page = staticmethod(lambda ingress_path="": b"<html><body>basis</body></html>")
    web.install_mode_web(App, tmp_path)

    handler = Handler()
    payload = b"mode=DEVELOPMENT&return_ui=1"
    handler.path = "/set-operating-mode"
    handler.headers = {"Content-Length": str(len(payload))}
    handler.rfile = io.BytesIO(payload)
    handler.send_body = lambda *args: (_ for _ in ()).throw(AssertionError("GUI request must not return raw JSON"))
    handler.do_POST()

    assert handler.redirect_status == 303
    headers = dict(handler.response_headers)
    assert headers["Location"].startswith("./?")
    assert "mode_notice=development_set" in headers["Location"]
    assert headers["Cache-Control"] == "no-store"
    assert handler.headers_ended is True


def test_card_distinguishes_basis_profile_from_effective_runtime():
    snapshot = _snapshot()
    snapshot["desired_profile"]["automatic_month_close_enabled"] = True
    snapshot["observed_profile"]["automatic_month_close_effective"] = False
    card = web.render_mode_card(snapshot)
    assert "Basisprofiel maandverwerking:</strong> AAN" in card
    assert "Effectieve maandverwerking:</strong> UIT" in card


def test_missing_runtime_measurement_renders_unknown():
    snapshot = _snapshot()
    snapshot["observed_profile"] = {}
    card = web.render_mode_card(snapshot)
    assert "Effectieve maandverwerking:</strong> ONBEKEND" in card


def test_card_contains_safe_fixed_notice_banner_script():
    card = web.render_mode_card(_snapshot())
    assert 'id="operating-mode-notice"' in card
    assert "development_set" in card
    assert "Release-hold vrijgegeven" in card
    assert ".textContent = message" in card
    assert ".innerHTML" not in card
    assert 'searchParams.delete("mode_notice")' in card
    assert 'searchParams.delete("mode_level")' in card
    assert "history.replaceState" in card


def test_gui_error_redirects_instead_of_json(tmp_path):
    class Handler:
        def do_POST(self):
            self.delegated = True

        def send_response(self, status):
            self.redirect_status = status

        def send_header(self, name, value):
            self.response_headers = getattr(self, "response_headers", []) + [(name, value)]

        def end_headers(self):
            self.headers_ended = True

    class App:
        pass

    App.Handler = Handler
    App.html_page = staticmethod(lambda ingress_path="": b"<html><body>basis</body></html>")
    web.install_mode_web(App, tmp_path)

    handler = Handler()
    payload = b"return_ui=1"
    handler.path = "/validate-release-hold"
    handler.headers = {"Content-Length": str(len(payload))}
    handler.rfile = io.BytesIO(payload)
    handler.send_body = lambda *args: (_ for _ in ()).throw(AssertionError("GUI error must not return raw JSON"))
    handler.do_POST()

    assert handler.redirect_status == 303
    location = dict(handler.response_headers)["Location"]
    assert "mode_notice=action_failed" in location
    assert "mode_level=error" in location
