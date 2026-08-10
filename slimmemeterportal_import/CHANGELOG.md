# Changelog

## 21.1.0
- Financial Action Runtime uitgebreid met expliciete runtime-gate-resolutie.
- Vaste volgorde: meetkwaliteit → officiële contractdata → opportunity-inputs → actionable.
- Automatische overgang zodra een externe gate werkelijk is gehaald.
- Geen gedeeltelijke of kandidaatwaarden mogen een actie publiceren.
- Ontbrekende financiële waarden blijven `Niet beschikbaar`; nooit €0-substitutie.
