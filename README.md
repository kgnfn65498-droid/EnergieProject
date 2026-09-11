# EnergieProject 32.4.41

32.4.41 is de structurele control-plane-closure van serie 32.4. De release vervangt de terugkerende watcher/Native-MCP bootstrapcirkel door één dedicated, begrensde `energie-control-plane` Container Station-container.

Kernpunten:

- alleen `watcher_recreate` en `native_mcp_reload` zijn toegestaan via de control-plane;
- beschermde acties blijven exact gekoppeld aan een expliciete Peter-goedkeuring;
- Projectmanager gebruikt runtime-first waarheid en voorkomt een tweede restart wanneer de Native MCP fingerprint al exact groen is;
- Chat/Voice/Nomad approval krijgt een immutable exact-decision ingress, met lokale PM als enige resolver;
- `energie-control-plane` is verplicht onderdeel van NAS Container Crash Recovery en restore-acceptance;
- ontwikkelartefacten horen onder `Inbox/Develop`; losse tijdelijke ontwikkelpaden worden uitsluitend via no-delete CLEARUP-quarantaine behandeld;
- release-audits tonen per concrete foutklasse een statusbol en echte reparatieronde-teller.

Productieplaatsing, architectuurwijzigingen en productie-restarts blijven protected actions. De gebruiker hoeft in de normale ontwikkel- en releaseflow geen Terminal te gebruiken.
