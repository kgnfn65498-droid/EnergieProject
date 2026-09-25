# Release Acceptance — 32.5.14

Status vóór live installatie: RELEASE CANDIDATE, niet live bewezen.

Verplicht GREEN vóór aanbieding:
1. exacte buildbasis 32.5.13 SHA `dee215af80e17ddd379d35755849f2358d6df831a9f6a9a05d218e0cad5e17af`;
2. exact-ZIP integriteit, manifests en fresh extract;
3. volledige 32.5.x regressies;
4. stale Docker file-bind simulatie: VERSIE-bind blijft predecessor terwijl controller + atomic state target release bewijzen; release-scoped reload moet toch exact één keer GREEN uitvoeren;
5. stale release-scoped request wordt bepaald via controller-eigenaarschap en veilig gearchiveerd;
6. atomic to_version/artifact mismatch blokkeert fail-closed;
7. legacy/manual Native-MCP reload blijft op VERSIE + Peter approval;
8. geen nieuwe paden/services en geen wijziging aan `Data/03_Systeem/Projectmanager/ClearUp/Exports`;
9. Type-2 delete/finalize blijft geblokkeerd;
10. exacte release-ZIP door dezelfde atomic prepare/swap/accept-validator als productie.

Na installatie vereist de ClearUp-vervolgstap live bewijs van de actuele Native-MCP fingerprint en echte download van 002–012.
