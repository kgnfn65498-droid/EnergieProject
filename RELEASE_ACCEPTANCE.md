# Release Acceptance — 32.5.16

Doel: ClearUp Type-2 002–012 volledig fail-closed en hervatbaar maken op de live 32.5.15 toestand.

Verplicht GREEN vóór aanbieding:
1. Buildbasis is exact fysieke 32.5.15 SHA256 `d95be5bb054c0e4b2fdd2d666a85f464fb934e2b4d20e29b3b365c03665810f3`.
2. Alle release-identiteiten zijn 32.5.16; PM-identiteit is `2.0.0-rc49`.
3. ClearUp_002 kan het bestaande MIGRATED_PENDING_VALIDATION-traject herstellen zonder bron/destinatie/delete te muteren.
4. Cutover-payloads worden byte-exact gereconstrueerd; onbewijsbare non-empty bytes blijven fail-closed.
5. Legacy fallback mag alleen op een bewezen GREEN-validatie plus twee identieke privileged quiescence snapshots van de preserved source.
6. PREPARED batches, inclusief ClearUp_012 met vluchtige locks, worden vóór migratie opnieuw gesnapshot; cutover recovery wordt vóór path-activation bevroren.
7. Alle path mappings 002–012 blijven na activatie autoritatief; aangepaste lange-leven writers/readers mogen retired Inbox-paden niet opnieuw creëren.
8. Recoverywijziging maakt eerdere externe ontvangstbevestiging automatisch ongeldig.
9. Finalize/delete blijft geblokkeerd totdat alle vereiste recovery-ZIP's exact zijn geverifieerd en extern expliciet bevestigd.
10. Volledige gesimuleerde 002–012 route prepare → migrate → validate → external-confirm → finalize is GREEN.
11. Relevante historische regressies, alle 32.5.x tests, compile, fresh-extract manifest/CRC en geïsoleerde atomic 32.5.15→32.5.16 acceptance zijn GREEN; bestaande split-state release-authority mag niet worden verzwakt.

Live eindacceptatie na installatie:
- 32.5.16 COMPLETE/readback;
- ClearUp_002 recovery refresh GREEN via echte ingress/consumer/watcher;
- 002–012 recovery-ZIP's deep-verify en werkelijk naar ChatGPT/workspace downloaden met lokale SHA256-readback;
- pas na Peters expliciete ontvangstbevestiging mogen afzonderlijke finalize/delete-acties worden hervat.
