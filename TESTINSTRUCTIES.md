# Testinstructies v10.7.0

1. Plaats `EnergieProject_v10.7.0.zip` in `EnergieProject_Inbox/incoming`.
2. Controleer dat de QNAP watcher de release verwerkt en archiveert.
3. Installeer/update add-on 10.7.0 in Home Assistant.
4. Open de GUI/Ingress en controleer dat deze normaal werkt.
5. Voer **Analyse-export** uit.
6. Download **release-diagnose**.
7. Controleer in de analyse:
   - `version` en `financial_projection.engine_version` = `10.7.0`;
   - `projection_detail` aanwezig is;
   - vóór 7 waargenomen dagen de status `blocked_insufficient_observation` blijft en prognosewaarden `null` blijven;
   - na de 7-dagengate kalendermaand-run-rate en de 30d low/base/high-band worden gepubliceerd;
   - `supplier_all_in` false blijft zolang officiële contractcomponenten ontbreken;
   - `epex_is_reference_only` true blijft.
8. Stuur analyse-JSON en release-diagnose terug. Bij geldige HA-validatie kan v10.8.0 autonoom worden gebouwd.

## Committekst
`v10.7.0 - deepen guarded financial forecast with calendar run-rate and scenario band`

## Resterend tot v11.0
Na v10.7.0: **2 productiestappen** — v10.8 officiële rapportgenerator-integratie, v10.9 eindvalidatie/consolidatie.
