import json
import re

CONTRACT_VERSION = '2026-09-11.v2'
VALID_THINKING_LEVELS = {'MIDDEL', 'HOOG'}
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
            'no_unnecessary_terminal_sudo_password_steps',
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
        ],
    }


def _positive_int(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


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
    result = canonical_contract()
    result.update(metadata)
    result.update({
        'required': required,
        'compliant': (not required) or not missing,
        'missing': missing,
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
