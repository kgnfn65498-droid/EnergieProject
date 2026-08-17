from __future__ import annotations

import html
import json
import os
from pathlib import Path
import secrets
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from operating_modes import command_path
from operating_mode_runtime import (
    attempt_emergency_release_hold,
    attempt_release_hold,
    operating_mode_tick,
)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}.{secrets.token_hex(3)}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _supports_live_runtime(app_module: Any | None) -> bool:
    if app_module is None or not hasattr(app_module, "APP_VERSION"):
        return False
    return callable(getattr(app_module, "operating_runtime_probe", None)) or hasattr(app_module, "WORKFLOW_LOCK")


def submit_operating_mode_command(
    project_root: Path | str,
    *,
    action: str,
    requested_mode: str | None = None,
    enabled: bool | None = None,
    transition_id: str | None = None,
    reason: str = "",
    issued_by: str = "gui",
    suspended_features: tuple[str, ...] | list[str] = (),
    confirmed_by_user: bool | None = None,
    app_module: Any = None,
) -> dict[str, Any]:
    root = Path(project_root)
    request_id = f"{issued_by}-{secrets.token_hex(6)}"
    payload: dict[str, Any] = {
        "schema_version": 1,
        "request_id": request_id,
        "action": action,
        "issued_by": issued_by,
    }
    if requested_mode is not None:
        payload["requested_mode"] = requested_mode
    if enabled is not None:
        payload["enabled"] = bool(enabled)
    if transition_id is not None:
        payload["transition_id"] = transition_id
    if reason:
        payload["reason"] = reason
    if suspended_features:
        payload["suspended_features"] = list(suspended_features)
    if confirmed_by_user is not None:
        payload["confirmed_by_user"] = bool(confirmed_by_user)

    _atomic_write_json(command_path(root), payload)
    live_app = app_module if _supports_live_runtime(app_module) else None
    snapshot = operating_mode_tick(root, app_module=live_app)
    return {"status": "ok", "request_id": request_id, "snapshot": snapshot}


def _pill(value: bool) -> str:
    return "AAN" if value else "UIT"


def _pill_optional(value: Any) -> str:
    if value is None:
        return "ONBEKEND"
    return "AAN" if bool(value) else "UIT"


_UI_NOTICE_CODES = {
    "development_set",
    "user_set",
    "maintenance_set",
    "auto_updated",
    "reconcile_ok",
    "release_hold_released",
    "release_hold_already_released",
    "release_hold_blocked",
    "emergency_release_done",
    "emergency_confirmation_required",
    "emergency_release_blocked",
    "action_failed",
}


def _ui_redirect_location(notice_code: str, level: str) -> str:
    code = notice_code if notice_code in _UI_NOTICE_CODES else "action_failed"
    safe_level = "success" if level == "success" else "error"
    return "./?" + urlencode({"mode_notice": code, "mode_level": safe_level})


def _send_ui_redirect(handler: Any, notice_code: str, level: str) -> None:
    handler.send_response(303)
    handler.send_header("Location", _ui_redirect_location(notice_code, level))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()


def _notice_result(
    endpoint: str, form: dict[str, list[str]], result: dict[str, Any]
) -> tuple[str, str]:
    if endpoint == "set-operating-mode":
        mode = str((form.get("mode") or [""])[0]).strip().upper()
        code = {
            "DEVELOPMENT": "development_set",
            "USER": "user_set",
            "MAINTENANCE": "maintenance_set",
        }.get(mode, "action_failed")
        return code, "success" if code != "action_failed" else "error"
    if endpoint == "set-operating-mode-auto":
        return "auto_updated", "success"
    if endpoint == "reconcile-operating-mode":
        return "reconcile_ok", "success"
    if endpoint == "validate-release-hold":
        status = str(result.get("status") or "")
        if status == "released":
            return "release_hold_released", "success"
        if status == "already_released":
            return "release_hold_already_released", "success"
        if status == "blocked":
            return "release_hold_blocked", "error"
        return "action_failed", "error"
    if endpoint == "emergency-release-hold":
        status = str(result.get("status") or "")
        if status == "released_emergency":
            return "emergency_release_done", "success"
        if status == "already_released":
            return "release_hold_already_released", "success"
        if status == "confirmation_required":
            return "emergency_confirmation_required", "error"
        if status == "blocked":
            return "emergency_release_blocked", "error"
        return "action_failed", "error"
    return "action_failed", "error"


def _notice_code(endpoint: str, form: dict[str, list[str]], result: dict[str, Any]) -> str:
    return _notice_result(endpoint, form, result)[0]


def render_mode_card(snapshot: dict[str, Any]) -> str:
    esc = lambda value: html.escape(str(value), quote=True)
    desired = snapshot.get("desired_profile") or {}
    drift = snapshot.get("drift") or []
    reason = snapshot.get("temporary_reason") or "—"
    reconcile = snapshot.get("reconciliation_status") or "unknown"
    auto = bool(snapshot.get("automatic_switching_enabled"))
    effective = snapshot.get("effective_mode") or "USER"
    base = snapshot.get("base_mode") or "USER"
    incoming = _pill(bool(desired.get("release_ingress_enabled")))
    basis_month = _pill(bool(desired.get("automatic_month_close_enabled")))
    observed = snapshot.get("observed_profile") or {}
    effective_raw = observed.get("automatic_month_close_effective") if "automatic_month_close_effective" in observed else None
    effective_month = _pill_optional(effective_raw)
    drift_text = "; ".join(str(item) for item in drift) or "geen"
    hold = snapshot.get("release_validation_hold") or {}
    hold_active = bool(hold.get("active"))
    hold_validation = hold.get("validation_status") or "—"
    hold_reconcile = hold.get("reconcile_status") or reconcile
    dev_session = _pill(bool(snapshot.get("development_session_active")))
    return f"""
<div class="card" id="operating-mode-card">
  <h2>Bedrijfsmodus</h2>
  <p><strong>Basis:</strong> {esc(base)} &nbsp; <strong>Actueel:</strong> {esc(effective)} &nbsp; <strong>Ontwikkelsessie:</strong> {dev_session}</p>
  <p><strong>Automatisch schakelen:</strong> {'AAN' if auto else 'UIT'} &nbsp; <strong>Reconciliation:</strong> {esc(reconcile)}</p>
  <p><strong>RELEASE VALIDATION HOLD:</strong> {_pill(hold_active)} &nbsp; <strong>Validatie:</strong> {esc(hold_validation)} &nbsp; <strong>Hold reconcile:</strong> {esc(hold_reconcile)}</p>
  <p><strong>Reden:</strong> {esc(reason)} &nbsp; <strong>Incoming verwerking:</strong> {incoming}</p>
  <p><strong>Basisprofiel maandverwerking:</strong> {basis_month} &nbsp; <strong>Effectieve maandverwerking:</strong> {effective_month}</p>
  <p><small>Drift: {esc(drift_text)}</small></p>
  <div id="operating-mode-notice" role="status" aria-live="polite" style="display:none;margin:10px 0;padding:10px;border:1px solid #bbb;border-radius:6px"></div>
  <div class="controls">
    <form method="post" action="set-operating-mode"><input type="hidden" name="return_ui" value="1"><input type="hidden" name="mode" value="USER"><button type="submit">USER</button></form>
    <form method="post" action="set-operating-mode"><input type="hidden" name="return_ui" value="1"><input type="hidden" name="mode" value="DEVELOPMENT"><button type="submit">DEVELOPMENT</button></form>
    <form method="post" action="set-operating-mode"><input type="hidden" name="return_ui" value="1"><input type="hidden" name="mode" value="MAINTENANCE"><button type="submit">MAINTENANCE</button></form>
    <form method="post" action="set-operating-mode-auto"><input type="hidden" name="return_ui" value="1"><input type="hidden" name="enabled" value="{'0' if auto else '1'}"><button type="submit">Automatisch schakelen {'UIT' if auto else 'AAN'}</button></form>
    <form method="post" action="reconcile-operating-mode"><input type="hidden" name="return_ui" value="1"><button type="submit">Reconcile</button></form>
    <form method="post" action="validate-release-hold"><input type="hidden" name="return_ui" value="1"><button type="submit">Release-hold valideren/vrijgeven</button></form>
    <form method="post" action="emergency-release-hold"><input type="hidden" name="return_ui" value="1"><input type="text" name="confirm" placeholder="NOODVRIJGAVE"><button type="submit">Noodvrijgave</button></form>
  </div>
  <script>
  (() => {{
    const searchParams = new URLSearchParams(window.location.search);
    const code = searchParams.get("mode_notice");
    const level = searchParams.get("mode_level");
    const messages = {{
      development_set: "DEVELOPMENT ingesteld",
      user_set: "USER ingesteld",
      maintenance_set: "MAINTENANCE ingesteld",
      auto_updated: "Automatisch schakelen bijgewerkt",
      reconcile_ok: "Reconcile OK",
      release_hold_released: "Release-hold vrijgegeven",
      release_hold_already_released: "Release-hold was al vrijgegeven",
      release_hold_blocked: "Release-hold kon niet veilig worden vrijgegeven",
      emergency_release_done: "Noodvrijgave uitgevoerd",
      emergency_confirmation_required: "Noodvrijgave vereist bevestiging",
      emergency_release_blocked: "Noodvrijgave is door veiligheidscontroles geblokkeerd",
      action_failed: "Actie niet uitgevoerd"
    }};
    const message = messages[code];
    if (message) {{
      const banner = document.getElementById("operating-mode-notice");
      if (banner) {{
        banner.textContent = message;
        banner.dataset.level = level === "success" ? "success" : "error";
        banner.style.display = "block";
      }}
      searchParams.delete("mode_notice");
      searchParams.delete("mode_level");
      const query = searchParams.toString();
      const cleanUrl = window.location.pathname + (query ? "?" + query : "") + window.location.hash;
      history.replaceState(null, "", cleanUrl);
    }}

    const modeCard = document.getElementById("operating-mode-card");
    if (modeCard) {{
      modeCard.querySelectorAll("form").forEach((form) => {{
        const uiOptIn = form.querySelector('input[name="return_ui"][value="1"]');
        if (!uiOptIn) return;
        form.addEventListener("submit", async (event) => {{
          event.preventDefault();
          const submitter = event.submitter;
          if (submitter) submitter.disabled = true;
          try {{
            const response = await fetch(form.action, {{
              method: "POST",
              body: new FormData(form),
              credentials: "same-origin",
              cache: "no-store",
              redirect: "follow"
            }});
            if (!response.ok || !response.url) throw new Error("mode action failed");
            window.location.replace(response.url);
          }} catch (_error) {{
            window.location.reload();
          }}
        }});
      }});
    }}
  }})();
  </script>
</div>
""".strip()


def inject_mode_card(page: bytes, card: str) -> bytes:
    marker = b"</body>"
    card_bytes = card.encode("utf-8")
    if marker in page:
        return page.replace(marker, card_bytes + b"\n" + marker, 1)
    return page + b"\n" + card_bytes


def _endpoint(path: str) -> str | None:
    for name in (
        "set-operating-mode",
        "set-operating-mode-auto",
        "reconcile-operating-mode",
        "validate-release-hold",
        "emergency-release-hold",
    ):
        if path == f"/{name}" or path.endswith(f"/{name}"):
            return name
    return None


def install_mode_web(app_module: Any, project_root: Path | str) -> None:
    root = Path(project_root)

    if not getattr(app_module, "_operating_mode_html_installed", False):
        raw_html_page = app_module.html_page

        def wrapped_html_page(*args, **kwargs):
            page = raw_html_page(*args, **kwargs)
            live_app = app_module if _supports_live_runtime(app_module) else None
            snapshot = operating_mode_tick(root, app_module=live_app)
            return inject_mode_card(page, render_mode_card(snapshot))

        app_module.html_page = wrapped_html_page
        app_module._operating_mode_html_installed = True

    handler_cls = app_module.Handler
    if getattr(handler_cls, "_operating_mode_post_installed", False):
        return
    raw_do_post = handler_cls.do_POST

    def wrapped_do_post(self):
        parsed_path = urlparse(self.path).path.rstrip("/")
        endpoint = _endpoint(parsed_path)
        if endpoint is None:
            return raw_do_post(self)
        return_ui = False
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
            form = parse_qs(self.rfile.read(length).decode("utf-8", errors="replace")) if length else {}
            return_ui = str((form.get("return_ui") or ["0"])[0]).strip() == "1"
            live_app = app_module if _supports_live_runtime(app_module) else None
            if endpoint == "set-operating-mode":
                mode = str((form.get("mode") or [""])[0]).strip().upper()
                result = submit_operating_mode_command(
                    root,
                    action="set_base",
                    requested_mode=mode,
                    issued_by="gui",
                    app_module=live_app,
                )
            elif endpoint == "set-operating-mode-auto":
                enabled = str((form.get("enabled") or ["0"])[0]).strip() == "1"
                result = submit_operating_mode_command(
                    root,
                    action="set_auto",
                    enabled=enabled,
                    issued_by="gui",
                    app_module=live_app,
                )
            elif endpoint == "reconcile-operating-mode":
                result = submit_operating_mode_command(
                    root,
                    action="reconcile",
                    issued_by="gui",
                    app_module=live_app,
                )
            elif endpoint == "validate-release-hold":
                if live_app is None:
                    raise RuntimeError("live runtime validation is unavailable")
                result = attempt_release_hold(
                    app_module,
                    root,
                    str(app_module.APP_VERSION),
                    issued_by="projectmanager_gui",
                )
            else:
                if live_app is None:
                    raise RuntimeError("live runtime validation is unavailable")
                confirmation = str((form.get("confirm") or [""])[0]).strip() == "NOODVRIJGAVE"
                result = attempt_emergency_release_hold(
                    app_module,
                    root,
                    str(app_module.APP_VERSION),
                    issued_by="user_gui",
                    confirmed=confirmation,
                )
            if return_ui:
                notice_code, notice_level = _notice_result(endpoint, form, result)
                _send_ui_redirect(self, notice_code, notice_level)
                return
            body = json.dumps(result, ensure_ascii=False).encode("utf-8")
            self.send_body(200, body, "application/json; charset=utf-8")
        except Exception as exc:
            if return_ui:
                _send_ui_redirect(self, "action_failed", "error")
                return
            body = json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False).encode("utf-8")
            self.send_body(400, body, "application/json; charset=utf-8")

    handler_cls.do_POST = wrapped_do_post
    handler_cls._operating_mode_post_installed = True
