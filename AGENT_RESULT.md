# AGENT_RESULT — EnergieProject

Status: IDLE
Schema: v1

Deze file bevat uitsluitend het overdraagbare resultaat van de actuele AGENT_TASK.

## Verplichte velden bij uitvoering
- task_id:
- executor:
- status: IN_PROGRESS | BLOCKED | GREEN | RED
- branch:
- commit:
- changed_files:
- root_cause:
- tests_run:
- test_result:
- acceptance_criteria_status:
- blockers:
- checkpoint:
- next_action:
- production_action_performed: NO
- restart_performed: NO
- terminal_required_from_peter: NO

## Regels
- Geen GREEN zonder aantoonbaar test-/read-backbewijs passend bij de taak.
- Geen productieclaim vanuit source-only bewijs.
- Duurzame lessen/regressie-evidence worden daarnaast naar WORK_LEDGER.md geschreven.
