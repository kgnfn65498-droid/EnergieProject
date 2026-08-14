# v32.0.33 July Ingress Fallback Design

## Doel
Zorgen dat de automatische maandafsluiting van 2026_07 niet meer stopt uitsluitend omdat `Data/01_Input/2026_07/HomeAssistant` nog niet bestaat, terwijl volledige SlimmeMeterPortal-data wel beschikbaar is.

## Scope
- Alleen de juli/maand-ingressfout oplossen.
- `publish_smp_import_to_nas_input()` maakt de vaste `HomeAssistant`-ingress veilig zelf aan als die ontbreekt.
- SMP blijft de volledige meterbron/fallback voor perioden waarin lokale P1/HomeWizard-historie ontbreekt.
- Ontbrekende lokale historische brondata blijft zichtbaar als partieel/niet beschikbaar; dit mag de SMP-publicatie niet blokkeren.
- De bestaande mapstructuur `Data/01_Input/YYYY_MM/HomeAssistant/SlimmeMeterPortal` blijft ongewijzigd.
- De duurzame completion-marker wordt alleen geschreven wanneer de normale workflow en finalisatie volgens bestaand contract succesvol eindigen.
- Geen wijziging aan augustus 2026; augustus blijft open.
- Geen handmatige of nieuwe oproep naar `finalize_month`.
- Geen wijziging aan Crash Recovery, release-watcher cleanup, GitHub-publicatie of iCloud-flow.

## Gedrag
1. Bij SMP-publicatie wordt `Data/01_Input/YYYY_MM` bepaald.
2. De submap `HomeAssistant` wordt met `mkdir(parents=True, exist_ok=True)` gegarandeerd.
3. De SMP-staging/publicatie gaat daarna door zoals nu.
4. Als lokale P1/HomeWizard/HA-historie voor een deel van de maand ontbreekt, blijft dat een bronkwaliteitswaarschuwing en geen infrastructurele fatal error zolang SMP bruikbaar is.
5. De scheduler kan daarna juli opnieuw verwerken; door de bestaande idempotency-marker stopt hij met juli zodra de maand echt succesvol is afgerond.

## Foutafhandeling
- Een onbeschrijfbare NAS-ingress blijft een harde fout.
- Een ontbrekende SMP-bronmap blijft een harde fout.
- Een ontbrekende `HomeAssistant`-map is geen fout meer; die wordt aangemaakt.
- Bestaande bestanden worden niet verwijderd of overschreven buiten de bestaande SMP-staging/publicatielogica.

## Teststrategie
- Regressietest: ontbrekende `HomeAssistant`-ingress + geldige SMP-bron => publicatie slaagt en map wordt aangemaakt.
- Regressietest: juli-scenario met ontbrekende lokale historie blokkeert SMP-publicatie niet.
- Negatieve test: onbeschrijfbare ingress blijft fout.
- Volledige pytest-suite.
- Exacte release-ZIP opnieuw testen.
- Installer-simulatie 32.0.32 -> 32.0.33.

## Succescriteria
- De exacte fout `HA-ingress ontbreekt voor 2026_07` kan niet meer optreden alleen omdat de map nog niet bestaat.
- 2026_07 kan met volledige SMP-data door de normale workflow heen, ook als lokale bronhistorie vóór halverwege juli ontbreekt.
- De completion-marker wordt pas na normale succesvolle afronding geschreven.
- Augustus blijft onaangeroerd en open.
