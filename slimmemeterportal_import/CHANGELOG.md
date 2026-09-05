# Changelog

## 32.4.4

- Projectmanager kan `nas_container_cr_create` terminalvrij uitvoeren via een private QNAP Docker TLS-koppeling.
- Certificaatsetup en connectoractivatie lopen uitsluitend via de lokale Home Assistant-ingress-UI; privésleutels worden nooit teruggerenderd of op de QNAP-projectshare opgeslagen.
- NAS Container CR maakt en verifieert de drie canonieke bestanden direct onder `Backups/NAS Container` en past keep-1 pas na GREEN toe.
- De CR-workflow stopt/herstart geen productiecontainers en vereist bewijs `PRODUCTION_CONTAINERS_CHANGED=NO`.
- Een eenmalige expliciete GUI-activatie herstart alleen `energie-filesystem-mcp`, zodat de bestaande externe MCP de nieuwe PM-intent uit de gedeelde App-code opnieuw laadt.
