# Changelog

## 32.4.62 — audit closure and autonomous successor release

- Carries the audited V61 publisher/delivery separation forward as the active successor path.
- Uses `/store/reload` + `/addons/self/info` + `/store/addons/<slug>/update`; no active `/addons/self/rebuild` dependency.
- Publication evidence remains exact even when Home Assistant delivery is still pending or fails.
- Processing remains transactional until exact GitHub identity and exact Home Assistant runtime are proven; Processed means COMPLETE.
- Corrects exact `failed_endpoint` diagnostics for the Supervisor store-update request.
