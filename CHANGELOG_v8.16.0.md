# Changelog v8.16.0

- Nieuwe append-only audittrail in `/config/output/audit_trail.jsonl`.
- Ieder auditrecord heeft een eigen SHA-256 en `previous_hash`; samen vormen de records een controleerbare hashketen.
- Schrijven is gesynchroniseerd met een audit-lock zodat gelijktijdige acties de keten niet kunnen breken.
- Auditregistratie voor maandworkflow-afronding, veilige productietests, schedulerinstellingen, scheduler-acceptatietests en productiecertificaatuitgifte/-beheer.
- Gezondheidsdashboard controleert audittrail en auditintegriteit.
- Operationele console toont recente auditrecords en biedt download van `audit_trail.jsonl`.
- Nieuwe auditrecords worden geblokkeerd als de bestaande keten beschadigd is.
- Bestaande workflow-, scheduler-, retry- en certificaatlogica blijft functioneel ongewijzigd.
- Geen wijzigingen aan rapportgeneratoren, definitieve outputnamen of Recovery Update-contract.
