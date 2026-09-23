# Platform Qualification — 32.4.66

Platform Qualification is geen releasegate tenzij een bevinding de actieve V66 releaseketen of settlement-observability raakt. Tests worden niet verwijderd, xfailed, overgeslagen of verzwakt om Release Acceptance groen te maken.

Bekende hostbeperkingen blijven:
- child-Python/sitecustomize volgorde bij `test_offline_test_guard`;
- restricted AF_UNIX/preexec/uid-gid capabilities in historische platformtests;
- legacy watcher/subprocess topologie kan hostafhankelijk zijn.

Finale rapportage onderscheidt altijd Release Acceptance van Platform Qualification.
