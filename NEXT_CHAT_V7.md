# Nieuwe-chat overdracht — EnergieProject 32.4.41

Actuele ontwikkellijn: 32.4.41 control-plane closure, gebouwd vanaf de exact bewezen 32.4.40-basis.

De dedicated `energie-control-plane` Container Station-container is de structurele Docker-socket beheerlaag. Hij heeft geen netwerk en accepteert uitsluitend `watcher_recreate` en `native_mcp_reload`, beide exact approval-gated. Watcher-contract en Native MCP runtimefingerprint zijn vóór de 32.4.41-build live groen bewezen; 32.4.41 borgt dat pad structureel in releasecode en Crash Recovery.

Vaste werkwijze: root-cause eerst, TDD RED→GREEN, geen gebruikers-Terminal, geen candidate-ZIP, exacte finale ZIP pas na fresh-extract regressie/compile/shell/manifest/atomic-simulatie. Ontwikkelwerk hoort onder `Inbox/Develop`; CLEARUP is uitsluitend reversible no-delete quarantine. Iedere release-audit gebruikt statusbol + echte reparatieronde-teller.

Na live installatie van 32.4.41 eerst volledige 32.4 closure bewijzen. Daarna roadmapvolgorde: ngrok security → Voice Mode E2E → nieuwe-chat/handover E2E → pas daarna 32.5/Cowork.
