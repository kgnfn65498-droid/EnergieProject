# Changelog

## 32.4.44 — ingress- en runtime-closure hardening

- Native MCP runtime-marker is uitsluitend v2 en schrijft via de bestaande schrijfbare `/system`-route; de oude import-time v1-writer naar read-only `/project` wordt verwijderd.
- Oude control-plane Native-MCP requests van een vorige release worden fail-closed gearchiveerd voordat een exact releasegebonden nieuwe request wordt geplaatst.
- Finale PM-heartbeat krijgt vlak vóór self-audit een verse timestamp zodat lange cycli niet ten onrechte RED eindigen.
- Oude MAINTENANCE closure-taken worden automatisch gesupersedeerd zodra een nieuwere release autoritatief actief is.
- Onderbroken-command issues worden gesloten zodra de canonieke command queue aantoonbaar geen INTERRUPTED items meer bevat.
- Exacte 32.4.43 verified ZIP blijft de enige buildbasis voor 32.4.44.
