## 32.0.7 - Ingress-statusfetch onderhoudsfix
- Gebruikt Home Assistant `X-Ingress-Path` voor interne API-fetches in de operationele console.
- Voorkomt `TypeError: Load failed` bij de GitHub-publicatiestatus onder Home Assistant Ingress/Safari.
- Behoudt de dedicated persistente Git-worktree en automatische HA→GitHub-publicatie.
- Geen wijzigingen aan energiegegevens, financiële gates, rapportlogica, NAS-layout of recoverybeleid.

# Changelog

## 32.0.7
- NAS-releaseketen blijft ZIP-only en automatisch.
- Alleen de Ingress-statusfetch is aangepast; overige productielogica blijft ongewijzigd.
