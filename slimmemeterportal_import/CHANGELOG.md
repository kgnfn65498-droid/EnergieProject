# Changelog

## 32.3.31

- Pagina-1-validator ondersteunt modelprovenance en krijgt een echte augustus end-to-end rendertest.
- Energiescore is numeriek en consistent op pagina 1 en pagina's 3–13.
- Hardcoded PV-factor 1,84 is verwijderd; PV-modelbasis komt aantoonbaar uit historische projectdata en blijft als model gelabeld.
- RecoveryManager `CLOSED` sluit een stale automatische maandretry af.
- Diagnose/health blokkeren false-green bij mislukte historische rapportherbouw of open retry.
