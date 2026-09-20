# AGENT_TASK — EnergieProject

Status: IDLE
Schema: v1

Deze file is de enige actieve werkbon tussen Spock/Chat, Work en Codex.

## Verplichte velden bij ACTIVE
- task_id:
- release:
- mode: DEVELOPMENT
- reasoning: MIDDEL | HOOG
- step: X/Y
- owner: SPOCK | WORK | CODEX
- goal:
- scope:
- do_not_change:
- proven_facts:
- required_tests:
- acceptance_criteria:
- stop_conditions:
- production_authority: NO | YES
- architecture_authority: NO | YES
- predecessor_artifact_required: NO | YES
- predecessor_artifact_identity:
- checkpoint_writeback_required: YES

## Agentregels
- ACTIVE zonder alle relevante velden = BLOCKED.
- Codex mag alleen code wijzigen binnen scope.
- Work mag Codex alleen inschakelen wanneer codewerk aantoonbaar nodig is.
- Buiten scope gevonden problemen worden gerapporteerd, niet stil meeverbouwd.
- Beschermde acties blijven afhankelijk van expliciete autoriteit.
