# Changelog

## 22.5.0
- Decision Publication Payload Runtime toegevoegd.
- Guarded beslisstatus wordt nu omgezet naar één expliciete, auditeerbare gebruikerspayload.
- Blocked en informational leveren uitsluitend `wait_for_data`; alleen publishable kan een financieel wijzigingsadvies dragen.
- Rapporthandoff voor managementsamenvatting, financiële KPI's en financiële aanbeveling is expliciet vastgelegd.
- Kandidaatwaarden komen nooit in de actiepayload; ontbrekende bedragen blijven null/`Niet beschikbaar`.
