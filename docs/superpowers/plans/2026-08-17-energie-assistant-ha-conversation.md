# Energie Assistant Home Assistant Conversation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build v32.3.8 with a read-only Home Assistant conversation agent that routes text Assist requests to the validated v32.3.7 Energie assistant backend, includes a persisted privacy switch, and uses Supervisor discovery without external port exposure.

**Architecture:** The existing SlimmeMeterPortal app remains the source of truth and gains a read-only `/api/assistant/respond` renderer plus Supervisor discovery publication for its already-internal port 8099. A HACS-compatible `custom_components/energie_assistant` integration registers one conversation entity and one privacy switch. The conversation entity has no `CONTROL` feature and only calls the discovered internal app endpoint; the privacy switch defaults OFF on first install and restores its last state.

**Tech Stack:** Python 3.12, Home Assistant 2026 conversation/config-entry APIs, standard-library urllib in the app, Home Assistant aiohttp client in the custom integration, pytest/static source-contract tests, shell release tooling.

## Global Constraints

- Release version is exactly `32.3.8`.
- Existing v32.3.7 seven-check read-only runtime acceptance must remain green.
- Conversation entity MUST NOT expose `ConversationEntityFeature.CONTROL`.
- Privacy gate defaults OFF on first install and must not stop energy collection.
- No external app port mapping, new filesystem rights, device-control, contract mutation, project write, or `finalize_month` behavior.
- August 2026 remains OPEN/PARTIAL; automatic month close remains OFF.
- Supervisor discovery may expose only internal host, port 8099, schema/version metadata; no credentials.
- `/api/assistant/respond` accepts only `query` and optional `session_id`, same size/security bounds as `/api/assistant/context`.
- User-visible response is deterministic and derived only from accepted assistant context; no LLM/cloud dependency.

---

### Task 1: Deterministic read-only response endpoint

**Files:**
- Create: `slimmemeterportal_import/rootfs/app/assistant_response.py`
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Test: `tests/test_v3238_assistant_response.py`

**Interfaces:**
- Consumes: accepted context dict from `ASSISTANT_ENGINE.process(query, session_id=...)`.
- Produces: `render_assistant_response(context: dict) -> str` and POST `/api/assistant/respond` JSON `{speech, context, schema, version}`.

- [ ] Write failing tests for gas/current month, previous month, finance-without-invoice-actual, apparatus KB provenance, and strict payload rejection.
- [ ] Run targeted tests and verify RED because renderer/route do not exist.
- [ ] Implement minimal deterministic renderer and read-only route using the existing payload limits/engine.
- [ ] Run targeted tests and verify GREEN.

### Task 2: Supervisor discovery publisher

**Files:**
- Create: `slimmemeterportal_import/rootfs/app/assistant_discovery.py`
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Modify: `slimmemeterportal_import/config.yaml`
- Test: `tests/test_v3238_assistant_discovery.py`

**Interfaces:**
- Produces: `publish_assistant_discovery(app_version: str) -> dict` with service `energie_assistant` and config `{host, port, ssl, api_path, version}`.
- Stores only the Supervisor discovery UUID in `/data/energie_assistant_discovery.json`; removes the previous UUID before republishing when available.

- [ ] Write failing tests for discovery declaration, no external port mapping, no secrets in discovery payload, and safe UUID replacement behavior.
- [ ] Verify RED.
- [ ] Implement minimal Supervisor self-info/discovery calls with `SUPERVISOR_TOKEN`; startup failure is non-fatal and keeps Voice not configured.
- [ ] Verify GREEN.

### Task 3: HACS-compatible Home Assistant integration

**Files:**
- Create: `custom_components/energie_assistant/manifest.json`
- Create: `custom_components/energie_assistant/const.py`
- Create: `custom_components/energie_assistant/__init__.py`
- Create: `custom_components/energie_assistant/config_flow.py`
- Create: `custom_components/energie_assistant/client.py`
- Create: `custom_components/energie_assistant/conversation.py`
- Create: `custom_components/energie_assistant/switch.py`
- Create: `custom_components/energie_assistant/strings.json`
- Create: `custom_components/energie_assistant/translations/en.json`
- Create: `custom_components/energie_assistant/translations/nl.json`
- Create: `hacs.json`
- Test: `tests/test_v3238_homeassistant_conversation_integration.py`

**Interfaces:**
- `EnergieAssistantClient.async_respond(query, session_id) -> dict` posts only to discovered internal base URL + `/api/assistant/respond`.
- `EnergieAssistantConversationEntity` supports all languages, has `ConversationEntityFeature(0)`, maps HA conversation id to backend session id, and returns backend `speech`.
- `EnergieAssistantPrivacySwitch` restores last state; first-install state is OFF; shared runtime gate controls conversation access only.

- [ ] Write failing static/isolated tests for manifest/config-flow, `CONTROL` absence, privacy default/restore contract, strict internal HTTP URL construction, and response mapping.
- [ ] Verify RED.
- [ ] Implement minimal integration with config flow handling `hassio` discovery and manual fallback URL.
- [ ] Verify GREEN.

### Task 4: Release identity, docs, regression and packaging

**Files:**
- Modify: `VERSIE.txt`, `slimmemeterportal_import/config.yaml`, app version constant, `CHANGELOG.md`, add-on changelog, `TESTINSTRUCTIES.md`, manifest/checksum files.
- Test: existing full suite plus v32.3.8 tests.

- [ ] Bump exact current release identity to 32.3.8 while preserving historical changelog content.
- [ ] Run assistant/security targeted tests.
- [ ] Run full pytest; require 0 failures.
- [ ] Compile every Python file and shell-check every shipped shell script with `sh -n`.
- [ ] Remove test caches, regenerate `MANIFEST.sha256` and `SHA256SUMS.json`, build ZIP.
- [ ] Fresh-extract ZIP; verify every manifest hash, exact version identity, full pytest, Python compile, shell syntax and ZIP integrity.
- [ ] Record Projectmanager candidate state and update current KB/Roadmap only after final verification.
