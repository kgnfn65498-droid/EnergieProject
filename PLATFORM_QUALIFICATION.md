# Platform Qualification — 32.4.67

Platform Qualification is geen releasegate tenzij een bevinding de actieve V67 releaseketen, executor-boundary of settlement-reconciliation raakt. Tests worden niet verwijderd, xfailed, overgeslagen of verzwakt om Release Acceptance groen te maken.

Bekende restricted-host beperkingen blijven apart gerapporteerd, waaronder child-Python/sitecustomize, AF_UNIX/preexec/uid-gid en historische subprocess-topologie. Een repository-wide/full-suite GREEN wordt alleen geclaimd wanneer die suite daadwerkelijk volledig GREEN draait.
