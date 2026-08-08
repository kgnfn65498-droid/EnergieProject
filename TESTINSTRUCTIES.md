# Testinstructies v10.5.18

1. Zet `EnergieProject_v10.5.18.zip` rechtstreeks in `EnergieProject_Inbox/incoming`.
2. Geen Terminal, geen hernoemen, geen tussenextensie.
3. Controleer automatische verwerking naar `processed`.
4. Installeer 10.5.18 in Home Assistant en herstart SlimmeMeterPortal Import één keer.
5. Klik **Download analysedata** en stuur het JSON-bestand.

Verwacht:
- `financial_status` staat bovenaan;
- juli heeft EPEX maar geen bruikbare P1-maanddata en krijgt dus geen geforceerde kosten;
- augustus heeft meetdata maar nog geen EPEX-maandbestand en krijgt dus geen geforceerde kosten;
- terugleververgoeding en supplier all-in blijven `null`;
- juli-EPEX blijft `gedeeltelijk` t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal. Gebruik GEEN handmatige Git-commit of Git-push.
