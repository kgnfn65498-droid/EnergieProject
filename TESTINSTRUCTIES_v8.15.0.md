# Home Assistant testinstructies v8.15.0

Functionele tests uitsluitend in Home Assistant.

1. Installeer/deploy v8.15.0 via de bestaande GitHub → Home Assistant workflow en start de add-on.
2. Open SlimmeMeterPortal en controleer dat bovenaan versie 8.15.0 staat.
3. Voor de productietest hoort het productiecertificaat `Niet geldig — missing` of `test_required` te tonen als er nog geen v8.15.0-certificaat bestaat.
4. Klik bij **Veilige productietest** op **Test automatische maandafsluiting nu** voor dezelfde eerder succesvol gebruikte testmaand.
5. Wacht tot de workflow in Home Assistant volledig gereed is. Controleer: preflight `ok`, workflow `completed` of `completed_warning`, finalization `ok`, schedulerinstelling ongewijzigd.
6. Vernieuw de pagina. Productiecertificaat moet nu `v8.15.0 · Afgegeven` tonen; Productiegereedheid moet geaccepteerd/gereed zijn.
7. Controleer **Productiecertificaten**: er moet een nieuwe regel voor 8.15.0 staan.
8. Klik **Controleer / herstel productiecertificaat**. Dit mag geen nieuwe maandworkflow starten en moet een geldige status teruggeven.
9. Klik **Download huidig productiecertificaat** en controleer dat een JSON-bestand beschikbaar is.
10. Controleer dat de planning Aan/Uit vóór en na de productietest exact hetzelfde is gebleven.

Stuur daarna screenshots van: (a) bovenste status/productiegereedheid, (b) Veilige productietest, (c) Productiecertificaten en (d) Retry Debug met certificaatregels. Daarna pas wordt een volgende versie gebouwd.
