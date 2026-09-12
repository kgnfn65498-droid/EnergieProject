# Changelog

## 32.4.45 — Native MCP runtime identity en klok-onafhankelijke coordinatie

- Native MCP runtime-fingerprint gebruikt contract v3 en omvat alleen code die daadwerkelijk door het Native-MCP-proces wordt geladen.
- Gewone Projectmanager-wijzigingen veroorzaken daardoor geen valse Native-MCP containerreload meer.
- Echte Native-MCP bronwijzigingen blijven fail-closed en gebruiken uitsluitend de bestaande beschermde exact releasegebonden restart-route.
- Runtime evidence blijft uitsluitend via `/system/Projectmanager/RuntimeEvidence` lopen; `/project` blijft read-only.
- Finale PM-coordinatie gebruikt cycle-generation + FINAL provenance als autoritatieve samenhang zodat NAS wall-clock skew dezelfde finale cyclus niet onterecht RED maakt.
- Exacte geverifieerde 32.4.44 ZIP SHA256 `0dc1312b75afd6bdf281c8fe881c765e3bcda658339418366e8cad2459e34df0` is de buildbasis.
