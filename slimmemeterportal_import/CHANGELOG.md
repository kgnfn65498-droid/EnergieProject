# Changelog

## 32.4.33

- CLEARUP hard-renames en restore worden na volledige HA safety-audit uitgevoerd via een expirerend, releasegebonden request naar de bestaande watchercontainer; geen verruiming van projectrootrechten.
- Watcher-executor verifieert release, atomic ACCEPTED, vrije validatie-hold, request-id/expiry en no-delete contract vóór mutatie en schrijft request-id-gebonden resultaatbewijs.
- De vaste bridge request/result-bestanden zijn observationeel zodat het control-plane zichzelf niet als nieuwe actieve dependency blokkeert; overige dependency-, hash-, rollback- en timeoutregels blijven intact.
