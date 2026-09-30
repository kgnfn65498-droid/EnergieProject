# CURRENT HANDOVER — Projectmanager / Knowledge Base / Index

Status: DEVELOPMENT / PR #11 / NIET GEACTIVEERD
Bijgewerkt: 2026-09-30

## Actuele scope
Uitsluitend Projectmanager + Knowledge Base + index/contextarchitectuur. Geen 32.5.30 development en geen releasewerk.

## Live readback
- Live productie: 32.5.29.
- Projectmanager mode: DEVELOPMENT.
- Live PM self-audit: RED door bestaande noncompliant development-task metadata en handover/build-contract drift.
- Live new-chat preflight rapporteert nog ten onrechte ready=true terwijl self-audit RED is; dit is expliciet onderdeel van de lopende structurele correctie.

## Onafhankelijke audit
Codex 6.0 Sol High bevestigde de root cause maar wees PR #11 eerste versie af. Kern:
aanwezigheid, discovery, selectie, delivery en toepassing zijn verschillende gates.

MUST FIX omvat truth/checkpoint-validatie, deterministic requirements/HOT lessons, compact Mandatory Core, evidence-bound resume, één consumer-gate, bounded context, invocation-bound receipt en behavioral E2E.

## Huidige branch
- Branch: `pm-kb-index-fix`
- PR: #11
- Geen merge/deployment/restart/productieactie uitgevoerd.

## Reeds gecorrigeerd op branch
- compact/bounded context package in plaats van volledige bronbestanden in snapshots;
- canonical JSON package identity;
- missing/empty mandatory sources en always-requirements fail-closed;
- deterministic ClearUp/capability/MCP/handover/recovery scopes;
- governing first-unproven action uit checkpoint/runtime reconciliation;
- equal-priority truth conflict fail-closed;
- corrupte/lege/equal-rank checkpoints geweigerd;
- stale/empty handover + next-action mismatch geweigerd;
- gecontroleerde FULL_KB inventory van beide KB-roots;
- capabilitystatus gekoppeld aan live bestandsaanwezigheid;
- bounded exact/lexical evidence + issue/capability evidence;
- context gate toegevoegd aan preflight/conversation/handover/API;
- invocation-bound delivery-receipt contract toegevoegd;
- behavioral evaluator toegevoegd;
- negatieve regressietests uitgebreid.

## Nog te bewijzen
- tests werkelijk uitvoeren op de huidige PR-head;
- bestaande regressies voor handover/API/context integraal GREEN;
- Native-MCP echte client exposure aan hetzelfde contextcontract;
- onafhankelijke Codex re-audit;
- echte clean-context/model-invocation E2E vóór runtime-GREEN.

## Hervatten
Lees AGENTS/Constitution/dit handover/WORK_LEDGER/AGENT_TASK/WORK_KNOWLEDGE_BOOTSTRAP, daarna huidige PR-head. Hervat vanaf eerstvolgende onbewezen acceptancegate. Niet terug naar 32.5.30.
