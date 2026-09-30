# 32.5.30 integration contract

Status: DEVELOPMENT ONLY. This work branch is a delta source, never the final release build basis.

## Authoritative final base
- Exact physical verified 32.5.29 release ZIP on NAS.
- Existing NAS staging Release32_5_30_KB_Index remains authoritative for Projectmanager/Knowledge Base/Master Index and MCP path/health work.

## Merge rules
- Never replace an already-staged 32.5.30 file blindly with this branch.
- For paths present in both NAS staging and this branch, perform semantic three-way integration from exact 32.5.29 predecessor and preserve both scopes.
- command_processor.py is explicitly MERGE_REQUIRED: retain PM/KB/Index staging changes and add the ROOT cleanup command hints.
- release_runtime_adapter.py remains authoritative from NAS MCP staging; this branch intentionally does not reconstruct that staged file.
- mcp_path_health_runtime_hotfix.py remains authoritative from NAS MCP staging; do not regenerate it from GitHub.
- MANIFEST.sha256 and SHA256SUMS.json must be regenerated only by the canonical builder from the final exact integrated workspace.

## Work-branch delta paths
- CHANGELOG.md
- DEV_CHECKPOINT_32.5.30.md
- VERSIE.txt
- release_test_contract.py
- slimmemeterportal_import/CHANGELOG.md
- slimmemeterportal_import/config.yaml
- slimmemeterportal_import/rootfs/app/main.py
- slimmemeterportal_import/rootfs/app/mode_entrypoint.py
- slimmemeterportal_import/rootfs/app/project_clearup.py
- slimmemeterportal_import/rootfs/app/project_clearup_auto.py
- slimmemeterportal_import/rootfs/app/project_hygiene.py
- slimmemeterportal_import/rootfs/app/projectmanager_v2/command_processor.py (MERGE_REQUIRED)
- slimmemeterportal_import/rootfs/app/projectmanager_v2/root_cleanup_32530.py
- slimmemeterportal_import/rootfs/app/projectmanager_v2/runtime_sources.py
- slimmemeterportal_import/rootfs/app/root_structure_policy.py
- tools/atomic_app_swap.py
- tools/ha_delivery_adapter.py
- tools/minimal_release_preflight.py
- tools/project_clearup_move_executor.py
- tools/release_artifact_builder.py
- tools/root_cleanup_executor_32530.py
- tests/test_v32530_root_cleanup.py
- tests/test_v32530_release_regressions.py

## Final gates
1. exact predecessor SHA readback;
2. semantic merge into NAS staging;
3. targeted tests;
4. historical regressions;
5. full isolated suite;
6. canonical ZIP build;
7. exact ZIP fresh-extract suite;
8. release to Incoming;
9. live HA acceptance;
10. /project alias + master-health + PM/KB/Index + ROOT cleanup live readback.
