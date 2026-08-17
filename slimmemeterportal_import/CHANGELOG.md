# Changelog

## 32.3.16

- Crash Recovery gebruikt tijdelijk MAINTENANCE en herstelt na veilige success/failure de oorspronkelijke USER/DEVELOPMENT-basis.
- DEVELOPMENT blijft persistent; alleen een onveilige gedeeltelijke mutatie houdt MAINTENANCE vast.
- Reboot tijdens gewone backup/verify herstelt failed-safe naar de oorspronkelijke basis.
- Rapportservicehistorie bewaart 13 maanden.
- RELEASE VALIDATION HOLD, watcher, scheduler en automatische maandafsluiting blijven inhoudelijk ongewijzigd.
