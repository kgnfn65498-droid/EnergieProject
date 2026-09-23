# Release Acceptance — 32.4.65

Release Acceptance toetst alleen de productie-releaseketen en de identiteit/fencing die daarvoor nodig zijn. Platform Qualification is apart en mag Release Acceptance niet kunstmatig groen of rood maken.

Verplichte V65-invarianten:
- exact V64 predecessor-artifact is cryptografisch gebonden aan SHA `875939a6d2112b69cf0b6da37d6c36216c80494aec00bbd78fdf59c37ea6acce`;
- frozen predecessor-source is een byte-exacte kopie van V64 `slimmemeterportal_import/rootfs/app/main.py`, met aparte source-SHA;
- predecessor publiceert opvolger naar exact GitHub target;
- enige Supervisor-actuator na publicatie is `/store/reload`;
- geen `/store/addons/<slug>/update`, install, rebuild of tweede actuatorpad;
- GitHub exact + predecessor HA runtime => duurzaam `WAITING_MANUAL_HA_UPDATE`;
- Processing blijft transactioneel owner tijdens die wachtfase;
- exact HA target => settlement, Processed, COMPLETE;
- settlement/archive blijft crash-safe en idempotent;
- N+1-regressie bewijst dat V65 zelf hetzelfde contract voor synthetische V66 uitvoert.

Release Acceptance vereist source- én exact-fresh-extract GREEN voor de releaseketenset. Een monolithische platform/full-suite GREEN is geen vereiste wanneer uitsluitend vooraf gedocumenteerde host-capability beperkingen optreden buiten de actieve releaseketen.
