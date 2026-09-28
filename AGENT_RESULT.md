# AGENT_RESULT — EnergieProject 32.5.26

Status: PRE-INSTALL VERIFICATION.

Exact predecessor: 32.5.25 SHA256 `bc667f11d6a22ef4588add6c213baff21c5b7ebd6591e5b4820732d5a9bbaf4a`.

32.5.26 bevat in één release:
- autonome evidence-bound Processing -> Processed settlement;
- vlakke `Inbox/failed` voor 32.5.26+ en alle bekende actieve failed-writers daarop aangepast;
- `Inbox/processing` uitsluitend transactioneel/on-demand en na settlement weer afwezig;
- originele vijfdelige Type-3 betekenis hersteld en 13 oorspronkelijke Type-3 groepen expliciet geïnventariseerd;
- finale Inbox-cleanup via de bewezen 32.5.x request-scoped privileged sideband (`sideband_bridge.py` + `project_clearup_move_executor.py`), dus geen nieuwe parallelle executor en geen heractivatie van de riskante 32.4 auto-ClearUp route;
- crash-cleanup, publisher-lock en ApprovalIngress naar canonieke systeemlocaties omgebonden;
- `Inbox/projectmanager_v2` uitsluitend als laatste guarded cleanupstap na receipt-proof;
- PM capability-provenance/current-truth zodat een nieuwe chat bestaande 32.5.x uitvoerroutes niet opnieuw kan missen;
- mandatory new-chat resume-context en retention-3 predecessor export/download capability.

Type-2 002-012 blijft CLOSED/GREEN en wordt niet opnieuw uitgevoerd. Productie is tijdens de build niet gemuteerd. Live-only gates blijven LIVE_REQUIRED totdat exact 32.5.26 via de normale Incoming-keten is geïnstalleerd.
