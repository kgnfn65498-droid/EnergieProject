# AGENT_RESULT — 32.5.27

Status: PREINSTALL GREEN

- Buildbasis: exact 32.5.26 SHA256 `e0ffa48b93e42b8ef09319775b1a54b8e25a9e7719a30d347762c1dcdeed71f5`.
- Processing is permanent: present+empty idle; only ZIP moves Incoming -> Processing -> Processed.
- Final Type-3/Inbox cleanup cannot remove Processing.
- Canonical GitHub publication state remains under `Data/03_Systeem/Projectmanager/ReleaseController/Publication`; no Inbox fallback.
- Canonical publication writer contract is normalized after completed-release reconciliation to directory `0777`, state files `0666` for the existing cross-identity HA writer.
- Type-2 002–012 remains CLOSED and was not rerun live.
- Selected regression acceptance: 876 passed + static 2 skipped.
- Python compileall GREEN; shell syntax 13/13 GREEN.
- Historical `test_v32524_incoming_tunnel.py` runtime simulation is not part of this release scope and times out in this isolated harness; its shell syntax remains GREEN.
- Repository offline-child guard test is harness-shadowed by `/opt/python-hooks/sitecustomize.py`; direct repository tests and static suite remain GREEN. This environment limitation is not treated as product evidence.
