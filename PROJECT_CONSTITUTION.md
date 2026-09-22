# PROJECT_CONSTITUTION — EnergieProject

Status: bindend, permanent.

## Harde ontwikkelcontracten
- ChatGPT/Projectmanager houdt technische regie; Work is uitvoer/orchestratie; Codex alleen bij aantoonbare technische meerwaarde met exacte vraag, scope en stopcriterium.
- Peter is geen menselijke transportlaag tussen ChatGPT, Work, Codex, NAS en Projectmanager.
- TDD: RED → GREEN. Bestaande regressietests worden niet verwijderd of versoepeld om een build groen te krijgen.
- Een release is niet geaccepteerd op basis van unittests alleen. De autonome live end-to-end releaseketen moet GREEN sluiten.
- Geen productie-installatie, restart/recreate of andere beschermde productieactie zonder expliciete autorisatie.
- Terminalgebruik door Peter is uitzondering. Als het echt nodig is: vooraf waarom, stap X/Y, verwachte duur, maximale duur, exact terug te sturen resultaat en resterend werk.
- Geen GitHub-reconstructie of productieboom als vervangende buildbasis.
- Geen state fabriceren of handmatig release-state/atomic/runtimebewijs op GREEN zetten.
- CR-retentie EnergieProject=1 en NAS Containers=1; oude geldige sets alleen reversibel/quarantaine, niet als shortcut verwijderen.
- Nieuwe chats beginnen niet opnieuw met reeds bewezen onderzoek.

## Releasecontract
### Tot en met 32.4.56
De historische releaseketen blijft uitsluitend relevant om de reeds live 32.4.56 minimaal en veilig af te sluiten. Er wordt geen nieuwe rescueketen voor gebouwd.

### Vanaf 32.4.57
- Incoming blijft de release-authority.
- Één ReleaseController bezit de lifecycle via `Inbox/release_controller/current.json`.
- Canonieke fasen: DETECTED → VERIFIED → PUBLISHING → INSTALLING → INSTALLED → RUNTIME_ALIGNING → VERIFYING → ACCEPTED → COMPLETE.
- Status is apart: ACTIVE / WAITING / BLOCKED / COMPLETE / ROLLED_BACK.
- `atomic_app_swap.py` blijft de install/rollback primitive en journal-evidence, maar is geen tweede lifecycle-owner.
- Operating mode, release_validation_hold, oude release_transition, CR, CLEARUP/hygiene, PM FINAL/self-audit, watcher heartbeat/contract, CommandIngress en stale PM tasks zijn geen release-critical gates.
- Native MCP self-heal is alleen release-scoped via exacte release_id/generation/artifact/version/fingerprint fencing.
- Geen compatibility shadow-state naar oude transition/hold.

## Crash-/chat-resumeprotocol
Wanneer Peter zegt **“opnieuw”**, “verder na crash”, of equivalent:
1. eerst persistent state/checkpoints lezen;
2. hoogste bewezen checkpoint + later gewijzigde staging/handover/ledger bepalen;
3. vanaf dat exacte punt hervatten;
4. geen reeds bewezen onderzoek, tests of buildstappen opnieuw uitvoeren tenzij nieuw bewijs daar expliciet om vraagt;
5. pas daarna een nieuw checkpoint opslaan.

Dit protocol geldt ook automatisch bij een nieuwe chat of onderbroken sessie.

## Persistente informatielagen
Een nieuwe chat leest in deze volgorde:
1. PROJECT_CONSTITUTION.md
2. CURRENT_HANDOVER.md
3. WORK_LEDGER.md
4. hoogste relevante checkpoint/worklog en later gewijzigde staging-evidence

Daarna uitsluitend aanvullende runtime-evidence die voor de eerstvolgende stap nodig is.


## Chat → Work → Codex agentcontract
- `AGENTS.md` is de verplichte agent-startinstructie en verwijst altijd naar deze Constitution als hoogste projectautoriteit.
- Iedere uitvoertaak loopt via exact één actuele `AGENT_TASK.md`; ontbrekende scope/acceptatie-/stopcriteria maken de taak BLOCKED.
- Uitvoerresultaat wordt machine- en mensleesbaar teruggeschreven naar `AGENT_RESULT.md`.
- Work orchestreert; Codex wijzigt alleen code wanneer de taak dat expliciet vereist.
- Agents mogen geen nieuwe architectuur of beschermde productieactie afleiden uit een algemene opdracht.
- Peter wordt niet gebruikt voor handmatige overdracht van opdrachten, bestanden of resultaten tussen Chat, Work en Codex wanneer GitHub die overdracht kan dragen.
- Nieuwe Chat/Work/Codex-sessies behandelen de persistente repositorylagen als continuïteitsbron; een sessiewissel reset geen ontwikkelcontract.

## Codex modelbeleid
- Voor EnergieProject-Codexwerk is de standaard en verplichte combinatie `gpt-5.6-terra` + `medium`.
- Geen autonome escalatie naar Astra, Sol of hoger reasoning-niveau.
- Hetzelfde beleid geldt voor plan mode en subagents.
- Bij onbeschikbaarheid of conflict met een hogere host/workspace-policy: fail-closed als `BLOCKED_MODEL_POLICY`; geen model-fallback zonder expliciet besluit van Peter.

## Usage-/tokenbeleid
- EnergieProject gebruikt standaard CONSERVE om session- en weekgebruik te beschermen.
- Work = Sol-Light voor orchestratie; Codex = Terra/Medium uitsluitend voor noodzakelijk codewerk.
- Geen dubbele analyse door Chat, Work en Codex: reeds persistente/bewezen informatie wordt hergebruikt.
- Geen parallelle subagents standaard en geen automatische modelverhoging.
- Reviews zijn head-SHA-idempotent: dezelfde onveranderde PR-head krijgt niet opnieuw een volledige agentreview.
- Bij door UI/Peter gemelde budgetdruk gelden de drempels uit AGENTS.md. Agents gokken nooit naar resterende quota.
- Budgetbesparing mag testwaarheid, releaseveiligheid of verplichte regressies niet omzeilen; in dat geval checkpointen en stoppen.
