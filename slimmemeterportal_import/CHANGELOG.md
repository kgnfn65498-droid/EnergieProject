# Changelog

## 32.4.3

- Projectmanager V2 embedded startup blijft via /app/mode_entrypoint.py en RuntimeV2 onder Inbox/projectmanager_v2/RuntimeV2.
- Projectmanager V2 auditreparatie: self-healing state, autonome regie, diepe health/self-audit en runtime-first truth.
- Single-writer control-plane: MCP schrijft uitsluitend CommandIngress; Peter-goedkeuringen lopen uitsluitend via lokale Home Assistant ApprovalIngress.
- Protected side effects blijven fail-closed totdat afzonderlijke veiligheidsgates aantoonbaar groen zijn.
