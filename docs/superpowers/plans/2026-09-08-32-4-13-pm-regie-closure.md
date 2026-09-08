# EnergieProject 32.4.13 PM Regie Closure

Doel: sluit uitsluitend de zeven tekortkomingen uit de grondige 32.4.12 Projectmanager-audit, zonder nieuwe architectuur of productieplaatsing.

1. Groene live release-validatie finaliseert atomic `LIVE_ACCEPTANCE` naar `ACCEPTED`; iedere fout blijft fail-closed.
2. Production/architecture-intake vereist expliciete approval ongeacht woordvolgorde.
3. Handoff-resultaten muteren task/roadmap/handoff als één herstelbare transactie.
4. Onbekende of blokkerende release-chain state kan niet groen zijn.
5. Definitieve RED self-audit opent/resolved een canoniek issue en volgt directe alert-policy.
6. Conversation Intake-summary telt alle classificaties per bericht.
7. Dezelfde progress truth wordt zichtbaar in HA-ingress GUI, status, handover en context.

Verificatie: nieuw TDD RED→GREEN-pakket, bestaande PM/release/GUI-regressies, volledige repositorysuite, 9 rapportgeneratortests, compile/shell/YAML, manifest, ZIP CRC en fresh-extract volledige herhaling.
