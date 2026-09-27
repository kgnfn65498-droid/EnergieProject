# 32.5.24 integrated final — installatiegrens

De normale installatie blijft één officiële `EnergieProject_v32.5.24.zip` via `Inbox/incoming`. Voor de huidige bekende 32.5.23 runtimeblokkade wordt vóór plaatsing van de ZIP uitsluitend het vooraf gevalideerde eenmalige tunnelrunbook gebruikt. De tunnel vereist lege Incoming/Processing en installeert 32.5.24 niet; hij herstelt alleen de bestaande control-plane/watcher/ReleaseController-keten naar GREEN/IDLE.

Geen alternatieve watcher/controller, geen handmatige move naar Processing, geen losse hotpatches en geen Type-2 delete. Een protected tunneluitvoering vereist expliciete approval voor exact die stop/start/recreate-actie. Na tunnel GREEN wordt de officiële ZIP één keer in Incoming geplaatst en de normale keten live gevalideerd.

# Installatie — EnergieProject 32.4.44

32.4.44 gebruikt uitsluitend de bestaande releaseketen. Plaats de volledig geverifieerde `EnergieProject_v32.4.44.zip` pas na expliciete productiegoedkeuring in de canonieke Incoming-route.

De watcher moet de ZIP zelfstandig verwerken. Definitie van succesvolle live acceptatie:

1. Incoming en Processing eindigen leeg zonder stuck release of installer lock.
2. NAS en Home Assistant rapporteren 32.4.44.
3. Native MCP expected/runtime fingerprint zijn identiek en `reload_required=false`.
4. Projectmanager self-audit is GREEN met een verse FINAL heartbeat.
5. Atomic state eindigt op `ACCEPTED`.
6. Geen handmatige `rm`, chmod, atomic accept of alternatieve publicatieroute is nodig.

Buildbasis: exacte geverifieerde 32.4.43 ZIP, SHA-256 `f1a4352a78ea2daf10359603fc4bd94c68b1f50d9f19694848adbb4ac28c54ec`.
