# EnergieProject v10.5.7

v10.5.6 bouwt voort op de in Home Assistant geteste v10.5.5-analysebasis en de bewezen stabiele releaseketen.

Deze release voegt de eerste echte stap van de v10.5 conversatie-/analysebasis toe: een gestandaardiseerde, read-only analysecontext uit de reeds aanwezige maanddata. Via `analysis-context` zijn maand-, kwartaal- en kalenderjaarwaarden machineleesbaar beschikbaar, inclusief kwaliteitsmetadata en markering van onvolledige perioden.

De automatische releaseketen QNAP -> GitHub -> Home Assistant, de maandworkflow, scheduler, retry/finalization, rapportgeneratoren en productiekern `9.4-core1` zijn niet gewijzigd.


## v10.5.7
De analysecontext bevat nu ook read-only historische EPEX-prijscontext per maand: aantal prijsrecords, gemiddelde, minimum en maximum voor elektriciteit en gas. Er worden bewust geen all-in energiekosten berekend zolang leverancierstarieven, belastingen en dekking niet volledig bewezen zijn.
