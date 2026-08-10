## v25.1.0 — guarded cumulative portfolio impact

- Voegt v25 stap 2/5 toe: Cumulative Portfolio Impact Runtime.
- Telt uitsluitend unieke, geboekte en gevalideerde Savings Ledger-resultaten op.
- Positieve én negatieve gerealiseerde effecten blijven behouden.
- Kandidaatwaarden, businesscase-schattingen en ongeboekte entries zijn uitgesloten.
- Gecorrigeerde ledgerregels behouden audittrail en mogen niet dubbel meetellen.
- Annualized portfolio totals blijven afhankelijk van de bestaande entry-level annualization gates.
- Releaseketen behouden: incoming -> QNAP processed -> automatische HA GitHub-publicatie -> Home Assistant update.
