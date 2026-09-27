# DEV CHECKPOINT — 32.5.25 replacement

## Buildbasis
Exact predecessor: 32.5.24 SHA256 `cb1b503606ad99f7b3796f3856c58da7c6066a45f4d375efdfd5d8f36e36701b`.
Rejected 32.5.25 SHA `85557cb336c1ca46242ba614f5df8f7db808fbbcab99961b0d4b856cc8473c64` is superseded.

## Scope
1. Physical Type-2 deletion must remove legacy 002–012 sources and detect any reappearance.
2. Close all discovered legacy writer leaks, including Native-MCP/CR log writers and long-lived GitHub publisher binding.
3. Keep external recovery confirmation privileged and fail-closed.
4. FULL_KB must include Decision Log/Development Changelog/Spock/KB audit/ticket inventory.
5. `new_chat_preflight` must prove `verder` continuity without manual re-explanation.
6. PM target rc60.

## Acceptance state
PRE-INSTALL until exact final ZIP fresh-extract passes all targeted/full/static/compile/shell/manifest/CRC gates. LIVE_REQUIRED remains for actual Incoming→Processed, publisher rebind, writer quiescence, Type-2 002→012 physical finalize and new-chat `verder` E2E.
## Chat-switch runtime reconciliation stage — GREEN
- TDD RED reproduced the two remaining continuity defects: target-live 32.5.25 was falsely conflicting with the pre-install 32.5.24 chat-switch checkpoint, and stale `ClearUp_001` remained `REVIEW_REQUIRED`.
- `current_truth_reconciliation` now recognizes an authoritative `energie_chat_switch_checkpoint_v2` whose exact `target_release` has become live as a completed handover transition, while unrelated checkpoint/live mismatches still fail closed.
- `StateReconciler` consumes the highest authoritative chat-switch checkpoint, supersedes the explicitly checkpoint-marked stale ClearUp task with checkpoint evidence, and creates one current 32.5.25 DEVELOPMENT closure task when no current task remains.
- The resumed task carries release build metadata, the checkpoint evidence ref and `new_chat_verder_e2e; verify canonical writer quiescence; then controlled Type-2 002-012 finalization` as next action.
- Targeted regression: 38/38 PM/state/new-chat tests GREEN; 32.5-series bounded regression chunks all GREEN (175 tests).
- No live state, container or Type-2 source was mutated during this stage.

