# Changelog

## 32.4.25 — history freshness en reversibele CLEARUP

- Verbruikshistorie-master valideert de nieuwste maand semantisch en repareert een stale master uitsluitend uit een valide maandarchief met atomische/hash-gecontroleerde publicatie.
- Nieuwe dependency-audited CLEARUP-quarantaine gebruikt harde same-filesystem renames; oude bronpaden verdwijnen volledig en conflict/actieve referentie faalt gesloten.
- Projectmanager V2 `2.0.0-rc22` meldt structurele cleanup-schuld en onbewezen ngrok-beveiliging read-only.
- Oude ProjectManagerV2-staging wordt per child dependency-audited zodat een actieve RuntimeV2-referentie alleen dat specifieke artifact blokkeert.
- CLEARUP-gating valideert de nieuwste CR-set op hash/manifest en gebruikt het aparte praktische Crash-Recovery-acceptatiebewijs als herstelketenbewijs.
- Native MCP-tunnel op `127.0.0.1:8000` geldt expliciet niet als beveiligde ngrok-architectuur; de bestaande dedicated externe PM-ingress blijft de beoogde grens.
- Productiekern blijft `9.4-core3`.
