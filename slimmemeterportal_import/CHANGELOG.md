## 32.5.8 — Native MCP command bridge + live activation proof

- Repareert de bewezen 32.5.7-fout waarbij `projectmanager_submit_command` de velden `classification_hint`, `artifact_path`, `release_version` en bronmetadata accepteerde maar buiten `conversation_intake`/`production_deploy` niet in CommandIngress schreef.
- De Native MCP runtime-contractpatch maakt command-forwarding generiek voor alle geïnstalleerde PM-intents en laat de bestaande secret/size/allowlist-gates intact.
- Een COMPLETE release blijft post-live geblokkeerd totdat de Native MCP-bron is gepatcht, de runtimefingerprint opnieuw exact is en de begrensde reload is bewezen.
- ClearUp_001 en Type-2 `prepare/export/migrate/validate/finalize/restore` kunnen daardoor werkelijk via dezelfde chat→MCP→Projectmanager-keten worden aangeroepen.
- Type-1 blijft exact allowlisted; Type-2 concrete plannen 002–012 blijven recovery-first en beschermen incoming/processing/processed/failed.

## 32.5.7

- TYPE2 ClearUp framework met prepare/export/migrate/finalize/restore via bestaand Projectmanager admin_update transport; release-mailboxen zijn hard beschermd.
- Projectmanager ClearUp_001 chat-apply route met fail-closed recovery/live revalidation en Inbox release-safety.

## 32.5.5
- Split-state recovery onderscheidt lokale install-predecessor van canonieke GitHub/HA-publicatiepredecessor.
- Pre-target publisher valideert beide domeinen exact en vereist geen tijdelijke lokale versie-impersonatie.
- Exact gepubliceerde targetcontracten blijven stabiel door installatie en handmatige HA-update heen.
- COMPLETE schrijft een machineleesbare post-live audit; settled IDLE is geen foutieve liveness-RED meer.
- Terminal/noodpatch-routes zijn geen normale releasedependency.

## 32.4.67
- COMPLETE settlement observability is now exact, self-healing and executor-boundary aware; manual HA update behavior is unchanged.

## 32.4.66
- Controller-owned publication settlement is now explicit in shared observability state; manual HA update behavior is unchanged.

## 32.4.65
- Consolidatie/hygiene bovenop live bewezen V64.
- Exact predecessor-provenance en manual-HA releasecontract behouden.

# Changelog

## 32.4.64

- Release-chain closure: manual HA update boundary, predecessor proof and N+1 regression coverage.
- Processing stays owned until exact GitHub + exact HA runtime; no automatic HA update/install/rebuild call.
- Crash/idempotent settlement and COMPLETE reconciliation are covered before release.
