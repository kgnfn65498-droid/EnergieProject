# Platform Qualification — 32.5.6

Platform Qualification is apart van Release Acceptance en is geen releasegate tenzij een bevinding de actieve releaseketen raakt. Tests worden niet verwijderd, xfailed, overgeslagen of verzwakt om de 32.5.6 releaseketen groen te verklaren.

Bekende restricted-host beperkingen in de repository-wide suite omvatten onder meer child-Python/sitecustomize-isolatie, AF_UNIX/preexec/uid-gid grenzen en historische tests die bewust een oude release-identiteit vastzetten. Zij moeten afzonderlijk worden gerapporteerd wanneer ze reproduceren.

Voor 32.5.6 is een platformbevinding alleen een releaseblocker wanneer zij de actieve releaseketen, split-state recovery, publication fencing, atomic install, manual-HA boundary, post-live audit of artifact-integriteit raakt.

Een repository-wide/full-suite GREEN wordt alleen geclaimd wanneer de volledige suite daadwerkelijk GREEN draait op de goedgekeurde geïsoleerde testomgeving. De fysieke release-ZIP blijft daarnaast onderworpen aan fresh-extract release-focused regressies en de productie-preflight.
