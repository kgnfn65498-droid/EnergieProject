# Testinstructies v10.2.0

1. Werk de Home Assistant-app bij naar v10.2.0. Normaal is alleen de app-update/herstart en GUI verversen nodig; **Opnieuw opbouwen** alleen als Home Assistant aantoonbaar een oude image blijft gebruiken.
2. Controleer dat bovenaan **versie 10.2.0** staat. De productiekern blijft `9.4-core1`; voer géén nieuwe automatische maandafsluitingstest uit.
3. Kijk naar **NAS migratie & release-inbox**. Zolang `Energie_NAS` nog niet als Home Assistant-share gekoppeld is, is `setup_required` een geldige uitkomst.
4. Klik **Download diagnosepakket** en stuur alleen die ZIP terug. Daarmee worden productie, infrastructuur, migratie-inventaris en release-inbox in één keer beoordeeld.
5. Verplaats of verwijder nog niets op NAS of iMac. v10.2 is uitsluitend inventarisatie/validatie.
