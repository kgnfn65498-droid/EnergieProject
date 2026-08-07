# Home Assistant testinstructies v8.16.1

## Doel
Alleen de twee UI-correcties uit v8.16.1 controleren. De audittrail-engine uit v8.16.0 is al met het gedownloade JSONL-bestand inhoudelijk bewezen.

## Test uitsluitend in Home Assistant
1. Commit en push v8.16.1 naar GitHub en deploy de add-on zoals gebruikelijk.
2. Open SlimmeMeterPortal en controleer bovenaan **versie 8.16.1**.
3. Controleer **Audittrail v8.16**. De bestaande auditrecords uit v8.16.0 moeten zonder nieuwe workflow zichtbaar zijn; integriteit moet `ok` zijn en het recordaantal moet groter dan 0 zijn.
4. Laat de pagina ongeveer 5 seconden open. Het auditblok moet gewoon zichtbaar blijven en via de automatische statusverversing actueel blijven.
5. Omdat een nieuwe softwareversie een eigen productiecertificaat vereist: voer **Test automatische maandafsluiting nu** één keer uit voor `2026-08`.
6. Wacht tot de test `completed` is. Controleer dat het auditblok automatisch nieuwe records toont zonder handmatig de hele pagina te verversen.
7. Controleer dat het productiecertificaat voor **v8.16.1** is afgegeven en Productiegereedheid weer **Productieklaar** is.
8. Klik één keer op **Controleer / herstel productiecertificaat**.
9. Je moet direct terugkomen in de gewone SlimmeMeterPortal-console bij **Productiecertificaten**; er mag geen losse JSON-pagina verschijnen.
10. Onder de knop moet **Certificaat gecontroleerd — geldig** staan. Alleen wanneer werkelijk herstel nodig was mag daar **Certificaat hersteld — geldig** staan.
11. Controleer dat in de audittrail een nieuw `production_certificate_management`-record verschijnt.
12. Controleer als laatste het Gezondheidsdashboard: `Audittrail ok`, `Auditintegriteit ok`, geldig productiecertificaat en certificaatversie `8.16.1`.

## Stuur screenshots van
- Productiestatus v8.16.1 na de productietest.
- Audittrail v8.16 met actuele records.
- Productiecertificaten direct na **Controleer / herstel productiecertificaat**.
- Gezondheidsdashboard.

Daarna wordt pas na beoordeling van de Home Assistant-resultaten verder gebouwd.
