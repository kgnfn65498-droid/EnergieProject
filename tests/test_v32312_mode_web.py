import io
import pathlib
import sys

APP_ROOT = pathlib.Path(__file__).resolve().parents[1] / "slimmemeterportal_import/rootfs/app"
sys.path.insert(0, str(APP_ROOT))

from operating_modes import Mode, load_mode_state
from operating_mode_web import (
    inject_mode_card,
    install_mode_web,
    render_mode_card,
    submit_operating_mode_command,
)


def test_gui_set_base_uses_same_command_contract(tmp_path):
    result = submit_operating_mode_command(
        tmp_path,
        action="set_base",
        requested_mode="DEVELOPMENT",
        issued_by="gui",
    )
    state = load_mode_state(tmp_path)
    assert result["status"] == "ok"
    assert state.base_mode is Mode.DEVELOPMENT
    assert state.effective_mode is Mode.DEVELOPMENT
    assert result["snapshot"]["reconciliation_status"] == "ok"


def test_mode_card_renders_manual_controls_and_status(tmp_path):
    snapshot = submit_operating_mode_command(
        tmp_path,
        action="reconcile",
        issued_by="gui",
    )["snapshot"]
    card = render_mode_card(snapshot)
    assert "Bedrijfsmodus" in card
    assert "USER" in card
    assert "DEVELOPMENT" in card
    assert "MAINTENANCE" in card
    assert "Automatisch schakelen" in card
    assert "Reconciliation" in card
    assert "Incoming verwerking" in card


def test_inject_mode_card_places_card_before_body_end():
    page = b"<html><body><h1>Bestaand</h1></body></html>"
    result = inject_mode_card(page, "<div id='operating-mode-card'>MODE</div>")
    assert result.index(b"operating-mode-card") < result.index(b"</body>")
    assert b"Bestaand" in result


def test_mode_post_endpoint_handles_set_mode_and_delegates_unknown(tmp_path):
    class Handler:
        def do_POST(self):
            self.delegated = True

    class App:
        pass

    App.Handler = Handler
    App.html_page = staticmethod(lambda ingress_path="": b"<html><body>basis</body></html>")
    install_mode_web(App, tmp_path)

    handler = Handler()
    payload = b"mode=DEVELOPMENT"
    handler.path = "/set-operating-mode"
    handler.headers = {"Content-Length": str(len(payload))}
    handler.rfile = io.BytesIO(payload)
    handler.send_body = lambda status, body, content_type: setattr(handler, "response", (status, body, content_type))
    handler.do_POST()
    assert handler.response[0] == 200
    assert load_mode_state(tmp_path).base_mode is Mode.DEVELOPMENT

    other = Handler()
    other.path = "/existing-action"
    other.headers = {"Content-Length": "0"}
    other.rfile = io.BytesIO(b"")
    other.delegated = False
    other.do_POST()
    assert other.delegated is True


def test_auto_endpoint_can_disable_automatic_switching(tmp_path):
    class Handler:
        def do_POST(self):
            self.delegated = True

    class App:
        pass

    App.Handler = Handler
    App.html_page = staticmethod(lambda ingress_path="": b"<html><body>basis</body></html>")
    install_mode_web(App, tmp_path)

    handler = Handler()
    payload = b"enabled=0"
    handler.path = "/set-operating-mode-auto"
    handler.headers = {"Content-Length": str(len(payload))}
    handler.rfile = io.BytesIO(payload)
    handler.send_body = lambda status, body, content_type: setattr(handler, "response", (status, body, content_type))
    handler.do_POST()
    assert handler.response[0] == 200
    assert load_mode_state(tmp_path).automatic_switching_enabled is False
