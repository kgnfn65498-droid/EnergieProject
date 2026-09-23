# Platform Qualification — 32.4.65

Platform Qualification is expliciet **geen releasegate** voor 32.4.65, tenzij een platformbevinding de actieve releaseketencode of een productie-invariant raakt. Tests worden niet verwijderd, xfailed, overgeslagen of verzwakt om Release Acceptance groen te maken.

## Bekende hostbeperkingen
- child-Python/sitecustomize volgorde kan `tests/test_offline_test_guard.py::test_child_python_installs_guard_before_application_imports` laten falen;
- restricted executors kunnen AF_UNIX socketcreatie, preexec en uid/gid-switching blokkeren in historische platformtests;
- legacy watcher/subprocess-tests kunnen op deze host hangen of andere import-topologie aannemen.

## Classificatie
- **Release defect**: raakt V65 releasecontroller, publication identity, manual-HA boundary, Processing/Processed settlement, artifact-integriteit of exact predecessor/N+1-contract.
- **Platform qualification issue**: vereist host-capabilities die de actieve V65 releaseketen niet gebruikt en reproduceert niet in de geïsoleerde release-acceptancetests.

Elke finale audit vermeldt beide statussen afzonderlijk. Er wordt geen repository-wide/full-suite GREEN geclaimd wanneer de hostbeperkingen dat niet ondersteunen.
