# Changelog

## 32.3.0 - Kwartierdata, NextEnergy-contractmodel en gesprekspartner
- Gebruikt voor de lopende maand de gevalideerde Home Assistant-kwartierreeks als primaire bron voor cumulatieve stroomimport, stroomexport en gas; sparse snapshots zijn alleen expliciete fallback.
- Rapporteert de echte beschikbare meetperiode, sampledekking en PARTIEEL-status en presenteert een lopende maand nooit als volledig.
- Voegt de officiële NextEnergy-contractcomponenten toe vanaf 16-07-2026: dynamische EPEX/TTF-formules, leveringskosten, belastingen, netbeheerkosten en Zonnebonusvoorwaarden.
- Voorkomt dubbele stroomopslag/energiebelasting doordat de live NextEnergy-stroomprijs al contractopslag + energiebelasting bevat.
- Houdt officiële factuuractuals strikt apart van gemodelleerde/waargenomen kosten en houdt het actuele projecttermijnbedrag (€150) apart van het oorspronkelijke contracttermijnbedrag (€118).
- Voegt een read-only gesprekspartnercontext toe met sessiecontext, periode-/domeinresolutie, bronkwaliteit, maximaal drie evidence-backed observaties en endpoints `/api/assistant/health` en `/api/assistant/context`.
- Voice/Assist-transport is bewust nog niet geactiveerd; eerst deze release live valideren.
- Geen wijziging aan automatische maandafsluiting; augustus blijft PARTIEEL en `finalize_month` wordt niet gebruikt.
