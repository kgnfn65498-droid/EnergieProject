# Changelog

## 32.3.1 - Kwartierdata, NextEnergy-contractmodel en gesprekspartner + MCP system-pad guard hotfix
- Onderhoudsrelease bovenop v32.3.0; energieanalyse, NextEnergy-contractmodel en gesprekspartner blijven inhoudelijk ongewijzigd.
- Release-watcher voert na installatie een fail-closed host-maintenance helper uit die de MCP `_system_path`-prefixguard plaatst en alleen de exact bekende dubbele acceptatiekopie opruimt.
- De MCP-container moet daarna één keer worden herstart om de nieuwe guard in het actieve Python-proces te laden.
- Augustus blijft PARTIEEL; automatische maandafsluiting blijft UIT en `finalize_month` wordt niet gebruikt.
