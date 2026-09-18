# Changelog

## 32.4.56 — process workspace, veilige cleanup en PM startup recovery

- Introduceert `Inbox/process` met `tmp`, `cache`, `active` en atomische procesregistratie; CLEARUP verplaatst alleen expliciet vrijgegeven of verlaten tijdelijke artefacten.
- Root-hygiëne classificeert bekende release/buildrommel voor reversibele CLEARUP en laat onbekend materiaal fail-closed staan; gewone release-rollbackretentie blijft 3.
- EnergieProject- en NAS Containers Crash Recovery behouden retentie=1 met validatie vóór oude sets naar quarantaine gaan.
- Embedded Projectmanager schrijft per cyclus duurzame RUNNING/GREEN/RED-evidence en kan na 15 minuten zonder verse huidige PM-cycle maximaal één add-on self-restart per uur aanvragen; geen hostrestart en geen gefabriceerde release-state.
- Behoudt de 32.4.55 `/share` atomic-mode readback-fix en automatische dismiss van herstelde HA-foutmeldingen.
- Target identity: EnergieProject 32.4.56 / Projectmanager 2.0.0-rc43.
