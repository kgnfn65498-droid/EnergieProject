# DEV CHECKPOINT — 32.5.26

- Baseline: exact 32.5.25 `bc667f11d6a22ef4588add6c213baff21c5b7ebd6591e5b4820732d5a9bbaf4a`.
- PM target: `2.0.0-rc61`.
- Type-2 002-012: CLOSED/GREEN, niet heropenen of opnieuw uitvoeren.
- ClearUp provenance: 32.5.x executorarchitectuur is leidend; 32.4 `project_clearup_auto` is HISTORICAL/FORBIDDEN voor Type-3/finale Inbox-cleanup.
- Type-3/finale Inbox: orchestration in PM, mutatie uitsluitend via bestaande privileged `sideband_bridge.py` + `project_clearup_move_executor.py`.
- Failed: platte structuur; corrupt/rejected/duplicates/rolled_back writers versiegebonden aangepast.
- Processing: idle absent; claim maakt on-demand; succesvolle/rolled-back settlement verwijdert lege map.
- Projectmanager legacy: ApprovalIngress canoniek; `Inbox/projectmanager_v2` pas als laatste cleanupactie.
- PM continuity: capability-registry wordt in development context/handover opgenomen en moet vóór `capability unavailable` worden geraadpleegd.
- Productiemutatie tijdens development: geen.
