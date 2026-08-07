# Home Assistant testinstructies v8.16.0

## Doel
Controleren dat de nieuwe hash-gekoppelde audittrail correct wordt opgebouwd zonder regressie in workflow, scheduler of certificaatbeheer.

## Test uitsluitend in Home Assistant
1. Commit en push v8.16.0 naar GitHub en deploy de add-on zoals gebruikelijk.
2. Open SlimmeMeterPortal en controleer bovenaan **versie 8.16.0**.
3. Controleer het **Gezondheidsdashboard**. `Audittrail` en `Auditintegriteit` moeten `ok` zijn. Direct na upgrade mag de audittrail nog 0 records bevatten.
4. Controleer het nieuwe blok **Audittrail v8.16**.
5. Voer **Test automatische maandafsluiting nu** één keer uit voor `2026-08`.
6. Wacht tot de productietest `completed` is en ververs de pagina.
7. Controleer dat het productiecertificaat voor **8.16.0** is afgegeven en geldig is.
8. Controleer in **Audittrail v8.16** dat minimaal records zichtbaar zijn voor `month_workflow`, `production_certificate` en `production_test`.
9. Klik **Controleer / herstel productiecertificaat**. Ververs daarna; er moet een record `production_certificate_management` bij zijn gekomen.
10. Klik **Instellingen opslaan** met exact dezelfde planningwaarden. Dit mag géén `scheduler_settings`-record toevoegen.
11. Verander tijdelijk alleen **Retry na (uur)** van 6 naar 7 en sla op. Er moet één `scheduler_settings`-record ontstaan. Zet daarna direct terug naar 6; er moet één tweede record ontstaan.
12. Controleer dat de planning uiteindelijk weer **Aan · dag 2 · 4:00 · retry 6u** is.
13. Klik **Download audittrail**. Het bestand `audit_trail.jsonl` moet worden gedownload.
14. Controleer opnieuw het Gezondheidsdashboard: `Audittrail ok` en `Auditintegriteit ok`.

## Stuur screenshots van
- Productiestatus v8.16.0.
- Audittrail v8.16 na de productietest.
- Gezondheidsdashboard inclusief Audittrail/Auditintegriteit.
- Planning nadat retry weer op 6 uur staat.

Daarna wordt pas na beoordeling van de Home Assistant-resultaten verder gebouwd.
