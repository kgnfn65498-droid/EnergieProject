# Dangerous / retired legacy code — 32.5.15

The files below are retained only for historical regression/rollback evidence and are **not active release dependencies**:
- `tools/legacy_install_adoption.py`
- `tools/native_mcp_reload_executor.py`
- `tools/cr_standard_native_mcp_hotfix.py`
- `tests/fixtures/pre57/**`
- `tests/fixtures/legacy57/**`

Rules:
1. They must not be imported or invoked by the active 32.5.9 release controller/runtime route.
2. They must never claim or move a current `Inbox/incoming` release.
3. They must never perform an automatic production restart or state mutation.
4. Re-activating or executing a retired legacy production path requires a new explicit Peter approval after the exact risk and scope have been stated.
5. Historical tests may import these files only inside isolated temporary test roots.
