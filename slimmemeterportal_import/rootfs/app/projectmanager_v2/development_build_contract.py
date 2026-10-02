import json
import re

CONTRACT_VERSION = '2026-10-02.v4'
VALID_THINKING_LEVELS = {'MIDDEL', 'HOOG'}
TERMINAL_REQUIRED_FIELDS = (
    'terminal', 'step_label', 'expected_duration_seconds', 'max_wait_seconds',
    'success_marker', 'stop_marker', 'return_required',
)
COMMAND_PROOF_FIELDS = (
    'target_state', 'command_sha256', 'parser_validation', 'check_only_preflight',
    'side_effects', 'dangerous_class', 'rollback', 'post_action_readback',
)

REQUIRED_BUILD_METADATA = (
    'thinking_level',
    'release_version',
    'estimated_total_seconds',
    'estimated_test_verification_seconds',
    'step_estimates_seconds',
    'original_estimate_recorded_at',
)


def canonical_contract():
    return {
        'contract_version': CONTRACT_VERSION,
        'cross_chat_required': True,
        'handover_requirements': [
            'load_before_development',
            'preserve_across_chat_voice_nomad',
            'report_thinking_level',
            'report_step_x_of_y',
            'report_elapsed_eta_test_time_learning_curve',
        ],
        'process_rules': [
            'isolated_staging_no_autonomous_production_write',
            'tdd_red_green_and_known_regressions',
            'audit_root_cause_before_structural_repair',
            'clean_staging_canonical_builder_exact_artifact_fresh_extract_atomic',
            'no_qnap_host_python3_assumption',
            'no_user_terminal_or_sudo_fallback',
            'no_autonomous_reboot_reset_destructive_admin',
            'explicit_save_requires_write_and_readback',
            'check_roadmap_kb_tasks_dependencies_before_completion_or_next_claims',
            'route_relevant_chat_voice_nomad_intake_to_pm',
            'persist_defect_rootcause_fix_regression_to_kb_and_pm',
            'chat_switch_never_resets_rules_architecture_platform_constraints',
            'roadmap_ledger_acceptance_matrix_required',
            'closed_cold_lessons_hot_checks_cold',
            'efficient_targeted_tests_then_one_exact_artifact_final_audit',
            'live_handover_is_primary_new_chat_truth',
            'exact_previous_verified_zip_required',
            'ask_peter_for_exact_zip_if_unavailable',
            'no_github_or_reconstruction_as_build_basis',
            'dynamic_all_requirements_discovery_required',
            'full_kb_runtime_enforcement_required',
            'master_development_index_required',
            'release_artifact_retention_three',
            'terminal_command_requires_preverified_command_proof',
            'stale_truth_conflict_fail_closed',
        ],
    }


def _positive_int(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def normalize_terminal_instruction(raw):
    if not isinstance(raw, dict):
        raw = {}
    required = raw.get('required') is True
    proof_raw = raw.get('proof') if isinstance(raw.get('proof'), dict) else {}
    proof = {
        'target_state': str(proof_raw.get('target_state') or '').strip(),
        'command_sha256': str(proof_raw.get('command_sha256') or '').strip().lower(),
        'parser_validation': str(proof_raw.get('parser_validation') or '').strip(),
        'check_only_preflight': str(proof_raw.get('check_only_preflight') or '').strip(),
        'side_effects': str(proof_raw.get('side_effects') or '').strip(),
        'dangerous_class': str(proof_raw.get('dangerous_class') or '').strip(),
        'rollback': str(proof_raw.get('rollback') or '').strip(),
        'post_action_readback': str(proof_raw.get('post_action_readback') or '').strip(),
    }
    result = {
        'required': required,
        'terminal': str(raw.get('terminal') or '').strip(),
        'step_label': str(raw.get('step_label') or '').strip(),
        'expected_duration_seconds': _positive_int(raw.get('expected_duration_seconds')),
        'max_wait_seconds': _positive_int(raw.get('max_wait_seconds')),
        'success_marker': str(raw.get('success_marker') or '').strip(),
        'stop_marker': str(raw.get('stop_marker') or '').strip(),
        'return_required': str(raw.get('return_required') or '').strip(),
        'reason': str(raw.get('reason') or '').strip(),
        'proof': proof,
    }
    missing = []
    if required:
        for field in TERMINAL_REQUIRED_FIELDS:
            if not result.get(field):
                missing.append(field)
        if not result['reason']:
            missing.append('reason')
    result['missing'] = missing
    result['compliant'] = (not required) or not missing
    return result


def normalize_build_metadata(raw, *, steps_total=None):
    if not isinstance(raw, dict):
        raw = {}
    thinking = str(raw.get('thinking_level') or '').upper().strip()
    estimates_raw = raw.get('step_estimates_seconds')
    estimates = []
    if isinstance(estimates_raw, (list, tuple)):
        for item in estimates_raw:
            value = _positive_int(item)
            if value is not None:
                estimates.append(value)
    result = {
        'contract_version': CONTRACT_VERSION,
        'thinking_level': thinking if thinking in VALID_THINKING_LEVELS else thinking,
        'release_version': str(raw.get('release_version') or '').strip(),
        'estimated_total_seconds': _positive_int(raw.get('estimated_total_seconds')),
        'estimated_test_verification_seconds': _positive_int(raw.get('estimated_test_verification_seconds')),
        'step_estimates_seconds': estimates,
        'original_estimate_recorded_at': str(raw.get('original_estimate_recorded_at') or '').strip(),
        'terminal_instruction': normalize_terminal_instruction(raw.get('terminal_instruction')),
    }
    if steps_total is not None:
        try:
            result['steps_total'] = max(1, int(steps_total))
        except (TypeError, ValueError):
            result['steps_total'] = 1
    return result


def _parse_key_values(text):
    values = {}
    for key in ('thinking_level', 'estimated_total_seconds', 'estimated_test_verification_seconds', 'original_estimate_recorded_at'):
        match = re.search(rf'(?im)\b{re.escape(key)}\s*[:=]\s*([^\s,;]+)', text)
        if match:
            values[key] = match.group(1).strip()
    match = re.search(r'(?im)\bstep_estimates_seconds\s*[:=]\s*([0-9,; ]+)', text)
    if match:
        values['step_estimates_seconds'] = [item for item in re.split(r'[,; ]+', match.group(1).strip()) if item]
    return values


def build_metadata_from_command(item):
    release = str((item or {}).get('release_version') or '').strip()
    if not release:
        return None
    raw = {'release_version': release}
    report = (item or {}).get('verification_report')
    if isinstance(report, dict):
        embedded = report.get('development_build_contract') if isinstance(report.get('development_build_contract'), dict) else report
        raw.update(embedded)
    else:
        text = str(report or '')
        if text.strip().startswith('{'):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                embedded = parsed.get('development_build_contract') if isinstance(parsed.get('development_build_contract'), dict) else parsed
                raw.update(embedded)
        raw.update(_parse_key_values(text))
    return normalize_build_metadata(raw, steps_total=(item or {}).get('steps_total'))


def _release_at_least(value, minimum):
    try:
        current = tuple(int(part) for part in str(value or '').split('.'))
        floor = tuple(int(part) for part in str(minimum or '').split('.'))
    except ValueError:
        return False
    return len(current) == 3 and len(floor) == 3 and current >= floor


def _enforce_command_proof(metadata, terminal_instruction):
    if _release_at_least(metadata.get('release_version'), '32.5.31') and terminal_instruction.get('required') is True:
        terminal_instruction['proof_missing'] = ['user_terminal_forbidden']
        terminal_instruction['proof_compliant'] = False
        terminal_instruction['compliant'] = False
        terminal_instruction['capability_status'] = 'CAPABILITY_BLOCKED'
        terminal_instruction['reason'] = terminal_instruction.get('reason') or 'NO_USER_TERMINAL'
        return terminal_instruction
    if terminal_instruction.get('required') is not True:
        terminal_instruction['proof_missing'] = []
        terminal_instruction['proof_compliant'] = True
        return terminal_instruction
    if not _release_at_least(metadata.get('release_version'), '32.5.24'):
        terminal_instruction['proof_missing'] = []
        terminal_instruction['proof_compliant'] = True
        return terminal_instruction
    proof = terminal_instruction.get('proof') if isinstance(terminal_instruction.get('proof'), dict) else {}
    missing = [field for field in COMMAND_PROOF_FIELDS if not proof.get(field)]
    sha = str(proof.get('command_sha256') or '')
    if sha and (len(sha) != 64 or any(ch not in '0123456789abcdef' for ch in sha.lower())):
        if 'command_sha256' not in missing:
            missing.append('command_sha256')
    terminal_instruction['proof_missing'] = missing
    terminal_instruction['proof_compliant'] = not missing
    if missing:
        terminal_instruction['compliant'] = False
    return terminal_instruction


def evaluate_build_contract(task, progress=None):
    task = task if isinstance(task, dict) else {}
    required = task.get('build_contract_required') is True
    metadata = normalize_build_metadata(task.get('build_metadata') or {}, steps_total=task.get('steps_total'))
    missing = []
    if required:
        for field in REQUIRED_BUILD_METADATA:
            value = metadata.get(field)
            if field == 'thinking_level':
                if value not in VALID_THINKING_LEVELS:
                    missing.append(field)
            elif field == 'step_estimates_seconds':
                if not value or len(value) != max(1, int(task.get('steps_total') or 1)):
                    missing.append(field)
            elif value in (None, '', []):
                missing.append(field)
    progress = progress if isinstance(progress, dict) else {}
    total = max(1, int(task.get('steps_total') or metadata.get('steps_total') or 1))
    step = max(1, min(total, int(task.get('step') or 1)))
    terminal_instruction = normalize_terminal_instruction(metadata.get('terminal_instruction'))
    terminal_instruction = _enforce_command_proof(metadata, terminal_instruction)
    result = canonical_contract()
    result.update(metadata)
    result.update({
        'required': required,
        'compliant': ((not required) or not missing) and terminal_instruction.get('compliant') is True,
        'missing': missing,
        'terminal_instruction': terminal_instruction,
        'terminal_compliant': terminal_instruction.get('compliant') is True,
        'step': step,
        'steps_total': total,
        'step_label': f'Stap {step}/{total}',
        'elapsed_seconds': progress.get('elapsed_seconds'),
        'estimated_remaining_seconds': progress.get('estimated_remaining_seconds'),
        'test_verification_actual_seconds': progress.get('test_verification_actual_seconds'),
        'planning_trend': progress.get('planning_trend') or 'insufficient_data',
        'step_actual_seconds': progress.get('step_actual_seconds') or {},
        'estimate_variance_seconds': progress.get('estimate_variance_seconds'),
        'development_efficiency': progress.get('development_efficiency') or {},
    })
    return result
