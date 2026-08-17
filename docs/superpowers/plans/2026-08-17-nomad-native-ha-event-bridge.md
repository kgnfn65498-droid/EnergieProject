# Nomad Native Home Assistant Event Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship v32.3.9 with a native Home Assistant sentence/event bridge for Nomad that uses the existing read-only assistant backend and no HACS/custom component.

**Architecture:** Home Assistant fires `energie_nomad_request` from a Sentence-trigger automation. The Energie add-on subscribes through the official Core WebSocket proxy, renders the existing information-only assistant response, and fires a correlated `energie_nomad_response`; the automation returns that with `set_conversation_response`. Privacy is the automation entity enabled/disabled state.

**Tech Stack:** Python 3, `websocket-client`, Home Assistant app Core WebSocket proxy, native HA Sentence automation, pytest, YAML/text static release gates.

## Global Constraints
- Base release is exact v32.3.8 artifact SHA-256 `3c37c871f39aad9e04358e5b953d62e75ad0e99b681fa411651834408a90ace0`.
- Release identity becomes `32.3.9` only after RED/GREEN bridge tests pass.
- Assistant visible name defaults to `Nomad` and remains configurable; technical id stays `energie_assistant`.
- No HACS, no custom component, no Terminal requirement, no `/config` mapping.
- Keep only `homeassistant_api: true`; remove `hassio_api`, `hassio_role` and Supervisor discovery.
- No device control, contract/payment/term mutation, project write, or month finalization.
- August 2026 remains OPEN/PARTIAL; `automatic_month_close_enabled: false`; never call `finalize_month`.
- Fixed Assist request/automation response gate remains 5 seconds.

---

### Task 1: Event protocol and payload validation

**Files:**
- Create: `slimmemeterportal_import/rootfs/app/assistant_event_bridge.py`
- Test: `tests/test_v3239_nomad_event_bridge.py`

**Interfaces:**
- Produces constants `REQUEST_EVENT`, `RESPONSE_EVENT`, `CORE_WEBSOCKET_URL`.
- Produces `validate_request_event(data) -> dict[str, str | None]`.
- Produces `NomadGreetingTracker.should_greet(session_id, now=None) -> bool`.

- [ ] Write tests that reject empty/oversized queries, unknown fields and invalid ids, and verify the 15-minute greeting idle rule.
- [ ] Run only the new tests and prove RED because the module does not exist.
- [ ] Implement the smallest pure validation/greeting layer.
- [ ] Run the new tests and prove GREEN.

### Task 2: Shared assistant response builder

**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/assistant_response.py`
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Test: `tests/test_v3239_nomad_event_bridge.py`

**Interfaces:**
- Produces `build_assistant_response_payload(engine, app_version, query, session_id=None) -> dict`.
- Existing HTTP `/api/assistant/respond` and the event bridge both call this helper.

- [ ] Add a failing test proving HTTP/event response construction shares one function and preserves schema/version/speech/session/context.
- [ ] Implement the helper and replace duplicated HTTP construction.
- [ ] Run targeted assistant response tests and new tests.

### Task 3: Home Assistant WebSocket bridge

**Files:**
- Modify: `slimmemeterportal_import/Dockerfile`
- Modify: `slimmemeterportal_import/rootfs/app/assistant_event_bridge.py`
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Test: `tests/test_v3239_nomad_event_bridge.py`

**Interfaces:**
- `HomeAssistantNomadBridge(stop_event, respond, display_name, greeting_enabled, greeting_idle_seconds)`.
- `run_forever()` authenticates with `SUPERVISOR_TOKEN`, subscribes only to `energie_nomad_request`, fires only `energie_nomad_response`, and reconnects with bounded backoff.

- [ ] Add failing fake-WebSocket tests for auth, subscribe, request correlation, fire_event response, reconnect and secret/query nonlogging.
- [ ] Add pinned `websocket-client>=1.8,<2` runtime dependency.
- [ ] Implement minimal synchronous bridge thread.
- [ ] Wire startup only after assistant runtime acceptance PASS.
- [ ] Run bridge and all assistant regression tests.

### Task 4: Remove superseded discovery/custom-component route and add native automation artifact

**Files:**
- Modify: `slimmemeterportal_import/config.yaml`
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Delete: `custom_components/energie_assistant/**`
- Delete: `hacs.json`
- Create: `00_Config/HomeAssistant/Nomad_automation.yaml`
- Test: `tests/test_v3239_nomad_native_ha_contract.py`

**Interfaces:**
- HA automation fires `energie_nomad_request`, waits for matching `energie_nomad_response`, and calls `set_conversation_response`.
- Automation entity on/off is the privacy control.

- [ ] Add RED static contract tests proving HACS/custom component/discovery permissions are absent and automation structure is bounded/read-only.
- [ ] Remove `hassio_api`, `hassio_role`, `discovery`; keep `homeassistant_api: true`.
- [ ] Remove unused custom component/HACS artifact and discovery startup call/import.
- [ ] Add Nomad automation YAML with `Nomad {vraag}` and `No mad {vraag}`, 5-second wait, correlated request id, stable session id, bounded parallel mode and timeout response.
- [ ] Run new native contract tests plus prior v32.3.8 security/runtime tests adjusted only where superseded by the approved native route.

### Task 5: Configurable Nomad greeting and release identity

**Files:**
- Modify: `slimmemeterportal_import/config.yaml`
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Modify: `slimmemeterportal_import/CHANGELOG.md`
- Modify: `CHANGELOG.md`
- Modify: `TESTINSTRUCTIES.md`
- Modify: `VERSIE.txt`
- Test: `tests/test_v3239_nomad_native_ha_contract.py`

**Interfaces:**
- Options: `assistant_event_bridge_enabled=true`, `assistant_display_name="Nomad"`, `assistant_greeting_enabled=true`, `assistant_greeting_idle_seconds=900`.

- [ ] Test defaults/schema and that technical identifiers do not contain the configurable display name.
- [ ] Add options/schema and consume them in bridge startup.
- [ ] Bump identity to 32.3.9 and add current-release documentation.
- [ ] Run targeted release/identity tests.

### Task 6: Full release verification and packaging

**Files:**
- Regenerate: `MANIFEST.sha256`, `SHA256SUMS.json` (using existing project release procedure)
- Create: `/mnt/data/EnergieProject_v32.3.9.zip`

- [ ] Run full pytest from the build tree; require 0 failures.
- [ ] Compile every Python file; require 100% success.
- [ ] Run `bash -n` on every shell file; require 100% success.
- [ ] Remove pytest/cache/build artefacts excluded by manifest policy.
- [ ] Regenerate manifest/checksum metadata using the established project tooling.
- [ ] Build ZIP and verify integrity.
- [ ] Extract ZIP to a new empty directory and rerun full pytest, compile, shell and manifest checks.
- [ ] Diff against v32.3.8 and verify changes are limited to native Nomad bridge, removal of superseded custom/discovery artifacts, version/docs/tests/dependency metadata.

### Task 7: Canonical Projectmanager/Knowledge Base candidate sync

**Files:**
- Write Projectmanager release candidate/state via scoped system writes.
- Update canonical `KnowledgeBase/ACTUELE_STATUS.md`, Roadmap, Master Index, Feature Catalog and Wijzigingslog through section-safe report tools.

- [ ] Record v32.3.9 as validated candidate only; keep production v32.3.8 until Incoming installation.
- [ ] Record HACS/custom component route as superseded and native event bridge as the approved route.
- [ ] Record Nomad identity/configurability and automation-toggle privacy model.
- [ ] Preserve August OPEN/PARTIAL and no-finalize invariant.
