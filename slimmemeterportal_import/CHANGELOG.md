# Changelog

## 32.4.24 — legacy closure en non-mutating core-certificering

- Recovery `OPEN` wordt gecombineerd met legacy/lifecycle-status; conflict met `CLOSED` of ontbrekende lifecycle-truth wordt `UNKNOWN` en blokkeert muterende maandflows fail-closed.
- Productiekern `9.4-core3` krijgt een autonome non-mutating core-safety acceptance zonder maandworkflow of maandmutatie.
- Certificaatbeheer verwerpt stale/tampered non-mutating bewijs en certificeert alleen volledig GREEN safety-evidence.
- Roadmap-migratie behandelt directory-permission-denial zonder startup-crash en gebruikt de goedgekeurde roadmap-spec read-only in runtime.
- Projectmanager V2 `2.0.0-rc21`; releaseketen en ngrok-ingressarchitectuur zijn verder ongewijzigd.
