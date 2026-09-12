# Testinstructies v32.4.44 — structurele release-closure

Minimale acceptatie vóór ZIP-uitgifte:

1. 32.4.44 regressies eerst RED gezien en daarna GREEN.
2. Native-MCP CR-hotfix verwijdert de oude v1 `/project/Inbox/...` writer en injecteert hem niet opnieuw.
3. Stale control-plane request van vorige release wordt veilig gearchiveerd; same-release conflict blijft fail-closed.
4. Finale heartbeat wordt vlak vóór self-audit ververst.
5. Stale MAINTENANCE closure-taak wordt door nieuwere autoritatieve release gesupersedeerd.
6. Project CR -> NAS CR -> CLEARUP closure-sequentie is autonoom en deterministisch.
7. Alle reguliere tests in batches GREEN; bekende skips blijven expliciet.
8. Release ZIP fresh-extract, CRC, member-safety, manifest en SHA256SUMS volledig verifiëren.
9. Kritieke 32.4.44 + 32.4.43/42/41 regressies op fresh extract nogmaals uitvoeren.
10. Productie blijft ongewijzigd tijdens de build/verificatie.
