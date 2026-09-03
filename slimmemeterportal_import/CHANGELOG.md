# Changelog

## 32.3.26

- Synchroniseert de automatische-maandafsluitingsschakelaar bij live GUI-refresh met de backendstatus.
- Productietest, scheduler-acceptatie en productiecertificaat worden in de GUI beoordeeld op productiekernrevision in plaats van releasenummer.
- Niet-geconfigureerde uitgeschakelde Enphase/EPEX-bronnen tellen niet meer als monitoring- of healthfout.
- Blokkeert een SMP full-month bron wanneer het maandtotaal fysiek lager is dan de overlappende P1-deelperiode; P1 blijft controlebron en de officiële historische rerender blijft fail-closed.
