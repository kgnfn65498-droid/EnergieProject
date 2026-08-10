# Testinstructies v19.3.0

1. Plaats `EnergieProject_v19.3.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `production_consolidation.v19_completion_gate.release_status = v19_complete_external_data_gates_remain`.
5. Controleer dat de drie v19-onderdelen `ready_guarded` zijn.
6. Onder 7 waargenomen dagen blijft het financiële advies geblokkeerd met expliciete reden.
7. Na 7 dagen mag de observatiegate automatisch openen; supplier-all-in blijft contract-gated.
8. Ontbrekende NextEnergy-componenten blijven: vaste leverancierskosten, leveranciersopslag, terugleververgoeding en gasformule.
9. Candidate-getallen mogen geen primaire rapportwaarden of beslisgrond worden.
10. EPEX blijft uitsluitend markt-/referentieprijs.
11. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.
12. Ontbrekende financiële waarden blijven `Niet beschikbaar`.
13. GUI, analyse-export, release-diagnose, watcher en maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
