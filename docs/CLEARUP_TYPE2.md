# ClearUp Type 2 framework — 32.5.7

32.5.7 contains a reusable fail-closed Type 2 ClearUp workflow. It does not invent or migrate a Type 2 candidate by itself: each concrete batch first gets an audited plan under `Data/03_Systeem/Projectmanager/ClearUp/Plans/ClearUp_xxx.json`.

## Fixed flow
1. `clearup_type2_prepare` — validate the plan and live release safety, copy the exact old source into recovery staging and build/verify a recovery ZIP. No source or destination mutation.
2. `clearup_type2_export_info` / `clearup_type2_export_chunk` — expose the verified ZIP through the existing Projectmanager `admin_update` transport so ChatGPT can provide it as a chat download without terminal or Native-MCP reload.
3. Peter stores the ZIP and confirms with normal language such as `akkoord`.
4. Code/config/path changes for the new destination are installed. Contract checks in the plan must prove the active release points at the new location and no longer at the old one.
5. `clearup_type2_migrate` — copy source to the definitive destination and hash-verify it. Source remains present; no delete yet.
6. Live readers/writers are validated. Evidence is stored in `Data/03_Systeem/Projectmanager/ClearUp/Validation/ClearUp_xxx.json` with GREEN status and the exact plan fingerprint.
7. `clearup_type2_finalize` — after explicit `akkoord`, the privileged QNAP watcher transactionally removes only the old sources. Destinations remain intact.
8. `clearup_type2_restore` — bounded rollback can recreate original sources from recovery staging without deleting the new destination.

## Safety
- Sources are restricted to Inbox but can never be `incoming`, `processing`, `processed` or `failed`.
- Destinations are restricted to `Data/03_Systeem/...`.
- ReleaseController must be COMPLETE and processing empty for every mutation.
- `incoming` and `processing` are byte/hash snapshotted and must remain unchanged.
- Every Type2 item requires explicit active contract checks before migration/finalize.
- Prepare happens before the code/path switch; migrate happens only after the new path contract is live.
- Finalize requires independent GREEN live-validation evidence.
- No terminal, `docker exec`, direct release-state mutation or manual Inbox bypass.

## Transport
No new externally exposed intent is required. All commands use the already available `admin_update` transport with these `classification_hint` values:
- `clearup_type2_prepare`
- `clearup_type2_export_info`
- `clearup_type2_export_chunk`
- `clearup_type2_migrate`
- `clearup_type2_finalize`
- `clearup_type2_restore`

The `artifact_path` field carries the ClearUp ID, e.g. `ClearUp_002`. This avoids depending on a Native-MCP tool reload merely to operate Type 2 ClearUp from chat.
