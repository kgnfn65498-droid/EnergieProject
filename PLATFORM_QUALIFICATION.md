# Platform Qualification — 32.5.15

Releaseblokkerend voor 32.5.15:
- exacte 32.5.14 buildbasis;
- alle 32.5.x regressies;
- historische Incoming/control-plane regressies die stale requests, watcher/reload en releasecontroller afdekken;
- post-migrate ClearUp recovery-refresh en diepe ZIP-verificatie;
- partial-download isolation;
- canonieke PM RuntimeV2;
- Python compile;
- canonical release builder, manifest/SHA/ZIP CRC en fresh-extract readback;
- atomic 32.5.14→32.5.15 acceptance.

Historische tests die aantoonbaar ook op de exacte 32.5.14-baseline rood zijn, worden als baselinebevinding gerapporteerd en niet groen gefabriceerd.

## Historische/platformtests
Historische of platformafhankelijke baseline-tests zijn **geen releasegate** wanneer ze aantoonbaar ook op exact 32.5.14 rood zijn. Zulke tests worden **niet verwijderd** en **niet verzwakt**; nieuwe regressies blijven releaseblokkerend.
