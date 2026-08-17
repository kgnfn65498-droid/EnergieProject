# Nomad native Home Assistant event bridge — design

## Goal
Connect the live v32.3.8 read-only Energie assistant backend to Home Assistant Assist without HACS, custom components, Terminal use, broad `/config` writes, or device-control capability.

## User-facing identity
- Visible/spoken assistant name: **Nomad**.
- Technical identifier remains `energie_assistant`.
- The visible name must remain configurable.
- Recognition aliases are configured in the Home Assistant sentence automation; initial aliases are `Nomad` and `No mad`.
- After an idle gap of 15 minutes, the first response for that Assist session is prefixed with `Nomad hier.`. The idle threshold and display name are add-on options.

## Architecture
1. A native Home Assistant automation uses a Sentence trigger such as `Nomad {vraag}`. Home Assistant sentence wildcards capture the free-text question in `trigger.slots.vraag`.
2. The automation fires the internal event `energie_nomad_request` with a correlation `request_id`, the captured query, and a stable session id derived from satellite/device identity with a safe fallback.
3. The existing Energie add-on maintains one authenticated WebSocket connection to `ws://supervisor/core/websocket`, using only the already-supported Home Assistant API proxy permission (`homeassistant_api: true`).
4. The add-on subscribes only to `energie_nomad_request`, validates the event payload, calls the existing read-only assistant engine, renders the same deterministic Dutch response used by `/api/assistant/respond`, and fires `energie_nomad_response` with the same `request_id` and speech.
5. The Home Assistant automation waits up to 5 seconds for the correlated response event and returns it with `set_conversation_response`. On timeout it returns a short fail-closed availability message.

## Privacy
The Home Assistant automation entity itself is the privacy switch. Turning the automation off disables Nomad sentence handling immediately while leaving all Energie data collection and the backend untouched. No extra helper or switch integration is required.

## Security and scope
- Information-only; no Home Assistant `CONTROL` conversation capability.
- No device actions, contract/term/payment changes, project writes, or `finalize_month` route.
- No HACS and no custom component in the release.
- No external port mapping.
- Remove the now-unneeded v32.3.8 Supervisor discovery declaration and `hassio_api`/`hassio_role` permissions.
- Keep `homeassistant_api: true` only, because the official Home Assistant app proxy uses it for Core REST/WebSocket access.
- `SUPERVISOR_TOKEN` is used only in memory for WebSocket authentication and is never logged or persisted.
- Request and response events are not persisted by the add-on. Queries are not logged.
- Payload validation rejects missing/empty/oversized queries, invalid request/session identifiers, and unsupported fields.

## Home Assistant automation artifact
Ship a copy/paste-ready native automation YAML under `00_Config/HomeAssistant/Nomad_automation.yaml`. It must:
- use Sentence triggers with wildcard `{vraag}`;
- fire `energie_nomad_request`;
- wait for `energie_nomad_response` matching `request_id`;
- return `speech` using `set_conversation_response`;
- use `mode: parallel` with a small bounded maximum;
- provide a timeout response;
- perform no device-control action;
- document that toggling the automation is the privacy control.

## Session behavior
Use `trigger.satellite_id` when available, then `trigger.device_id`, else `home-assistant-assist`. This preserves follow-up context such as `En vorige maand?` for the same Assist origin. The add-on greeting tracker prefixes `Nomad hier.` only after the configured idle interval.

## Failure behavior
- WebSocket disconnect: reconnect with bounded exponential backoff; backend/data collection continue.
- Invalid request event: ignore it and emit no mutating action.
- Assistant error: emit a short `status=error` response without internal traceback or secrets.
- Home Assistant timeout: automation returns `Nomad is tijdelijk niet beschikbaar.`.
- Privacy off: automation disabled, so no Nomad request event is created.

## Acceptance
Offline release gates: RED/GREEN TDD, targeted bridge tests, full pytest, Python compile, shell syntax, manifest/hash and fresh-extract verification.

Live gates after normal Incoming install:
1. production identity matches release;
2. existing assistant 7/7 runtime acceptance remains PASS;
3. `hassio_api`, `hassio_role`, discovery and custom component are absent;
4. event bridge connects/subscribes without logging token/query;
5. user imports/pastes the supplied automation through Home Assistant GUI;
6. text Assist `Nomad hoeveel gas heb ik deze maand gebruikt` returns an information-only answer;
7. follow-up `Nomad en vorige maand` retains session context;
8. automation OFF blocks Nomad while quarter-hour energy collection continues;
9. automation ON restores Nomad;
10. no device-control or mutating route is exposed.

Speech-to-text, text-to-speech selection, wake word and physical Assist Satellite hardware remain outside this release.
