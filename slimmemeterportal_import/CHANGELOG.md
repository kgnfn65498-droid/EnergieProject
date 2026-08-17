# Changelog

## 32.3.17

- GitHub-publicatie is idempotent wanneer MAIN al op de targetrelease staat vóór live installatie.
- Exacte targetrelease wordt zonder extra push als gepubliceerd afgerond.
- Targetbron met uitsluitend afwijkende gegenereerde release-metadata wordt veilig gesynchroniseerd; echte bronafwijking blijft fail-closed.
- Operating-mode, RELEASE VALIDATION HOLD, Crash Recovery, watcher, scheduler en maandafsluiting zijn ongewijzigd.
