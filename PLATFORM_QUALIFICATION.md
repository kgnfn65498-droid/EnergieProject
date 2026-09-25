# Platform Qualification — 32.5.9

Deze kwalificatie is geen releasegate voor historische/platformtests die reeds rood of sandbox-afhankelijk waren in de exacte 32.5.8-basis. Zulke baselinebevindingen worden afzonderlijk gerapporteerd en niet groen gefabriceerd.

Wel releaseblokkerend voor 32.5.9:
- nieuwe of gewijzigde 32.5.9-tests;
- volledige ClearUp Type1/Type2 002..012 ketentests;
- stale-control-plane regressies;
- protected-action/legacy-isolatie;
- Python compile;
- manifest/SHA/ZIP CRC/fresh-extract verificatie;
- geen nieuwe regressies ten opzichte van de exacte 32.5.8-baseline in gecontroleerde batches.

Geen test weakening: historische failures worden niet verwijderd of stil genegeerd; waar een nieuwe eis een oud contract bewust vervangt, wordt de test expliciet aangepast en de reden gedocumenteerd.
