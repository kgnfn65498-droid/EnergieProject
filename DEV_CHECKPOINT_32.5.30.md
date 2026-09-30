# DEV CHECKPOINT — 32.5.30

Status: DEVELOPMENT_ONLY_NOT_RELEASED
Basis for this work branch: GitHub main at 32.5.29 commit fee16a075a8238ae9fde5ac450195c467cd0cd14.
Authoritative final build basis remains the exact verified physical 32.5.29 release ZIP on NAS; this branch is not a release/build source.

## Scope preserved for final 32.5.30 integration
- Existing NAS staging: Projectmanager + Knowledge Base + Master Index deterministic fail-closed context chain.
- Existing NAS staging: native MCP /project root-alias correction and bounded master-health scan.
- ROOT cleanup completion:
  - canonical top-level Rollback/;
  - retain newest three normal rollbacks;
  - migrate retained legacy root rollbacks into Rollback/;
  - quarantine/delete only proven excess/debt through the existing privileged ClearUp sideband;
  - move legacy root CLEARUP under Data/03_Systeem/Projectmanager/ClearUp;
  - PM commands: inventory, preview, recovery, export, external confirmation, apply, restore, finalize;
  - recovery-first for non-rollback destructive debt;
  - atomic rollback_path follows rollback migration.
- 32.5.29 ingress regressions:
  - exact release identity across VERSIE/config/main/mode entrypoint/release_test_contract;
  - github_publisher_binding.py must import/use project_system_path;
  - split-state remote_predecessor_exact pre-target wait is bounded;
  - normal manual Home Assistant update wait remains intentionally unbounded.

## GitHub Actions incident
A temporary development workflow was added only to the work branch and produced three failed runs/notifications. It has been removed. Do not re-add or rerun it. Existing run logs proved all changed modules compiled; targeted ROOT tests were 2 passed / 2 failed solely because the test fixture did not create active App module paths. The fixture was corrected afterwards without rerunning Actions to avoid further notifications.

## Current work-branch evidence
- Current head after ROOT/release hardening: d38310ce5434ac86a068576738ba2f042f7ff9b5.
- Temporary Actions workflow has been removed and must not be reintroduced.
- Historical run 36780695606 compiled all changed 32.5.30 modules successfully; its targeted ROOT test result was 2 passed / 2 failed because only the test fixture lacked active App module directories. That fixture has since been corrected.
- Additional static regressions now cover failed/candidate root debt, unclassified root fail-closed behavior, build-time release identity, publisher system-path binding, bounded pre-target split-state wait, and unbounded manual HA wait.
- The canonical release builder now fail-closes on split runtime identity and on a missing publisher system-path binding import.
- ROOT finalize now fences migrated targets, checks atomic rollback-path identity, performs a bounded resurrection soak, and refuses unsafe/symlinked restore paths.
- No claim of final GREEN until exact NAS predecessor build + full isolated suite + fresh-extract + live acceptance.
## Safety
- No merge to main.
- No PR.
- No HA/NAS restart.
- No production mutation.
- No GitHub reconstruction as final release basis.
