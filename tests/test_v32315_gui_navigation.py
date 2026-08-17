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
