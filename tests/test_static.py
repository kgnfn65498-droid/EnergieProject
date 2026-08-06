from pathlib import Path
import ast
import json
import re

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "slimmemeterportal_import"

def test_python_syntax():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    ast.parse(source)

def test_version_matches():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    main = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    cfg_version = re.search(r'version:\s*"([^"]+)"', config).group(1)
    app_version = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', main).group(1)
    assert cfg_version == app_version == "6.6.0"

def test_required_files():
    required = [
        "config.yaml", "build.yaml", "Dockerfile", "DOCS.md",
        "CHANGELOG.md", "rootfs/app/run.sh", "rootfs/app/main.py"
    ]
    for rel in required:
        assert (ADDON / rel).is_file(), rel

def test_no_appledouble_files():
    assert not any(p.name.startswith("._") for p in ROOT.rglob("*"))


def test_resume_and_retention_configured():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert "resume_incomplete_month" in config
    assert "retention_months" in config

def test_manifest_and_cancel_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "build_manifest" in source
    assert 'action="cancel"' in source
    assert "cancel_requested" in source

def test_no_hardcoded_api_key():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "871687940008186827" not in source
    assert "871717710000201497" not in source


def test_integrity_features_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "verify_manifest" in source
    assert "integrity_report.json" in source
    assert 'action="verify"' in source

def test_integrity_config_present():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert "verify_after_import" in config
    assert "fail_on_validation_errors" in config


def test_duplicate_and_summary_features_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "duplicate_count" in source
    assert "build_month_summary" in source
    assert "month_summary.json" in source

def test_duplicate_config_present():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert "detect_duplicates" in config
    assert "create_month_summary" in config


def test_workflow_features_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "workflow_source_status" in source
    assert "build_transfer_bundle" in source
    assert "Energie_Maandimport_" in source

def test_workflow_config_present():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert "create_transfer_bundle" in config
    assert "workflow_mode" in config
    assert "full_month_workflow" in config


def test_homewizard_features_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "homewizard_get" in source
    assert "collect_homewizard_snapshot" in source
    assert 'action="homewizard-snapshot"' in source
    assert "/api/v1/data" in source

def test_homewizard_config_present():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert "homewizard_enabled" in config
    assert "homewizard_devices" in config
    assert "homewizard_sample_seconds" in config


def test_enphase_epex_features_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "run_enphase_import" in source
    assert "run_epex_import" in source
    assert 'action="enphase-import"' in source
    assert 'action="epex-electricity-import"' in source
    assert 'action="epex-gas-import"' in source

def test_enphase_epex_config_present():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    for key in (
        "enphase_enabled",
        "enphase_source_url",
        "epex_electricity_enabled",
        "epex_electricity_url",
        "epex_gas_enabled",
        "epex_gas_url",
    ):
        assert key in config


def test_central_validation_features_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "validate_central_workflow" in source
    assert "trigger_report_generation" in source
    assert "central_validation.json" in source
    assert "report_trigger_result.json" in source
    assert 'action="central-validation"' in source

def test_report_trigger_config_present():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert "report_trigger_enabled" in config
    assert "report_trigger_url" in config
    assert "report_trigger_token" in config
    assert "require_all_core_sources" in config


def test_self_test_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "run_self_test" in source
    assert 'action="self-test"' in source
    assert "installation_ready" in source

def test_install_guide_present():
    assert (ROOT / "INSTALL.md").is_file()


def test_repository_url_is_real():
    repository = (ROOT / "repository.yaml").read_text(encoding="utf-8")
    assert "https://github.com/kgnfn65498-droid/EnergieProject" in repository
    assert "example.invalid" not in repository

def test_local_build_labels_present():
    dockerfile = (ADDON / "Dockerfile").read_text(encoding="utf-8")
    assert "io.hass.version" in dockerfile
    assert "io.hass.type" in dockerfile
    assert "io.hass.arch" in dockerfile

def test_ingress_restricted():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "172.30.32.2" in source
    assert "_client_allowed" in source

def test_secret_files_ignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore
    assert ".pytest_cache/" in gitignore


def test_usage_path_template_present():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "usage_path_template" in config
    assert "build_usage_path" in source

def test_run_import_does_not_read_results_before_assignment():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    run_import = next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "run_import"
    )
    first_update = next(
        node for node in ast.walk(run_import)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "update_state"
    )
    names = {node.id for node in ast.walk(first_update) if isinstance(node, ast.Name)}
    forbidden = {
        "integrity", "month_summary", "transfer_bundle",
        "central_validation", "report_trigger_result",
    }
    assert not (names & forbidden)

def test_final_state_contains_completed_artifacts():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'last_integrity_status=integrity.get("status")' in source
    assert "last_summary=month_summary" in source
    assert "last_central_validation=central_validation" in source


def test_top_level_launcher_present():
    launcher = ADDON / "run.sh"
    assert launcher.is_file()
    text = launcher.read_text(encoding="utf-8")
    assert "launcher gestart" in text
    assert "python3 -u /app/main.py" in text

def test_docker_uses_top_level_launcher():
    dockerfile = (ADDON / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY run.sh /run.sh" in dockerfile
    assert 'CMD ["/run.sh"]' in dockerfile

def test_startup_logging_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Python-app v%s initialiseert." in source


def test_manifest_excludes_dynamic_control_files():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"integrity_report.json"' in source
    assert '"report_trigger_result.json"' in source

def test_manifest_created_after_central_validation():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    run_start = source.index("def run_import")
    run_source = source[run_start:source.index("def next_run", run_start)]
    assert run_source.index('write_atomic_json(target / "central_validation.json"') < run_source.index(
        'write_atomic_json(target / "manifest.json"'
    )

def test_bundle_created_after_integrity_report():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    run_start = source.index("def run_import")
    run_source = source[run_start:source.index("def next_run", run_start)]
    assert run_source.index('write_atomic_json(target / "integrity_report.json"') < run_source.index(
        "build_transfer_bundle("
    )

def test_verify_endpoint_uses_targeted_legacy_repair():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def verify_latest_with_legacy_repair" in source
    assert "result = verify_latest_with_legacy_repair(target)" in source
    assert "affected.issubset(LEGACY_MANIFEST_MUTABLE_FILES)" in source

def test_integrity_failure_does_not_rewrite_validation_after_manifest():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    run_start = source.index("def run_import")
    run_source = source[run_start:source.index("def next_run", run_start)]
    manifest_pos = run_source.index('write_atomic_json(target / "manifest.json"')
    assert 'write_atomic_json(target / "validation_report.json"' not in run_source[manifest_pos:]


def test_production_release_has_no_experimental_stage():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert 'version: "6.6.0"' in config
    assert "stage: experimental" not in config

def test_disabled_sources_are_skipped_in_central_validation():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    validation_start = source.index("def validate_central_workflow")
    validation_end = source.index("def trigger_report_generation", validation_start)
    validation = source[validation_start:validation_end]
    assert "if not enabled:" in validation
    assert "continue" in validation
    assert "Optionele bron niet gereed" not in validation

def test_disabled_report_trigger_is_not_selftest_warning():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    selftest_start = source.index("def run_self_test")
    selftest_end = source.index("def core_source_requirements", selftest_start)
    selftest = source[selftest_start:selftest_end]
    assert 'add("report_trigger_config", "ok", "Bewust uitgeschakeld.")' in selftest

def test_startup_runs_selftest_in_background():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def startup_self_test()" in source
    assert "result = run_self_test()" in source
    assert "threading.Thread(target=startup_self_test, daemon=True).start()" in source


def test_homewizard_device_info_and_measurement_endpoints():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'return homewizard_request(host, "/api", timeout)' in source
    assert 'return homewizard_request(host, "/api/v1/data", timeout)' in source

def test_homewizard_month_csv_writer_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def persist_homewizard_month_rows" in source
    assert '"P1e.csv"' in source
    assert '"P1g.csv"' in source
    assert "HOMEWIZARD_CSV_FIELDS" in source

def test_homewizard_output_name_is_case_sensitive_and_safe():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def safe_homewizard_output_name" in source
    assert "Path(configured).name" in source
    assert "name != configured" in source

def test_homewizard_schema_supports_output_name():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert "output_name: str" in config

def test_snapshot_records_csv_files():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'snapshot["month_csv_files"] = written_csv' in source
    assert "homewizard_last_csv_files" in source


def test_homewizard_discovery_configuration_present():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert "homewizard_discovery_enabled" in config
    assert "homewizard_discovery_cidr" in config
    assert "homewizard_discovery_timeout_seconds" in config

def test_homewizard_discovery_is_limited_to_slash_24():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "network.prefixlen < 24" in source
    assert "beperkt tot één IPv4 /24-netwerk" in source

def test_homewizard_discovery_endpoint_and_ui_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"/homewizard-discover"' in source
    assert "Detecteer HomeWizard-apparaten" in source
    assert "def discover_homewizard_devices" in source

def test_discovery_does_not_modify_options():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    start = source.index("def discover_homewizard_devices")
    end = source.index("def homewizard_request", start)
    block = source[start:end]
    assert 'write_atomic_json(CONFIG_ROOT / "homewizard_discovery.json"' in block
    assert "OPTIONS_PATH" not in block

def test_homewizard_classifier_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def classify_homewizard_device" in source
    assert "def discover_homewizard_device" in source


def test_ipaddress_import_present_at_module_scope():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert any(line.strip() == "import ipaddress" for line in source.splitlines())

def test_runtime_dependency_guard_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def validate_runtime_dependencies()" in source
    assert 'ipaddress.ip_network("192.0.2.0/24")' in source
    assert "validate_runtime_dependencies()" in source


def test_central_storage_constants_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'CONFIG_ROOT = Path("/data")' in source
    assert 'OUTPUT_ROOT = Path("/config/output")' in source
    assert 'STATE_PATH = Path("/config/state.json")' in source
    assert 'OPTIONS_PATH = Path("/data/options.json")' in source

def test_storage_guard_present_and_used():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def ensure_storage_paths()" in source
    assert "CONFIG_ROOT.mkdir(parents=True, exist_ok=True)" in source
    assert "OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)" in source
    assert "ensure_storage_paths()" in source

def test_discovery_logs_result_count():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "HomeWizard-detectie afgerond" in source

def test_discovery_error_includes_type():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"type": type(exc).__name__' in source


def test_default_homewizard_cidr_matches_project_network():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert 'homewizard_discovery_cidr: "192.168.1.0/24"' in config

def test_container_network_is_never_used_for_discovery():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'ipaddress.ip_network("172.30.0.0/16")' in source
    assert "continue" in source

def test_discovery_status_is_tracked():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'homewizard_discovery_status="running"' in source
    assert 'homewizard_discovery_status="completed"' in source
    assert 'homewizard_discovery_status="error"' in source

def test_discovery_ui_shows_network():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "HomeWizard netwerk" in source
    assert "Scanbereik:" in source


def test_homeassistant_api_enabled():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert "homeassistant_api: true" in config

def test_homeassistant_states_uses_supervisor_proxy():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'HOME_ASSISTANT_STATES_URL = "http://supervisor/core/api/states"' in source
    assert 'os.environ.get("SUPERVISOR_TOKEN"' in source
    assert '"Authorization": f"Bearer {token}"' in source

def test_homewizard_mapping_uses_serial_and_friendly_name():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def map_discovery_to_home_assistant" in source
    assert '"serial": serial' in source
    assert '"home_assistant_friendly_name"' in source
    assert "friendly_device_name" in source

def test_homewizard_mapping_output_names():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"Heater KANTOOR": "Heater kantoor"' in source
    assert '"Heater WOONKAMER": "Heater woonkamer"' in source
    assert '"Heater LOUNGE": "Heater lounge"' in source
    assert 'return f"{normalized} Skt.csv"' in source

def test_effective_devices_use_mapping():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def effective_homewizard_devices" in source
    assert "if effective_homewizard_devices(options):" in source
    assert "for device in effective_homewizard_devices(options):" in source


def test_homeassistant_energy_sampling_config_present():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert "homeassistant_energy_sampling_enabled" in config
    assert "homeassistant_energy_sample_seconds" in config
    assert "enphase_entity_id" in config
    assert "nordpool_entity_id" in config
    assert "nextenergy_entity_id" in config

def test_homeassistant_energy_entities_are_project_entities():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert "sensor.envoy_122335051406_lifetime_energy_production" in config
    assert "sensor.nordpool_kwh_nl_eur_3_10_021" in config
    assert "sensor.nextenergy_actuele_stroomprijs" in config

def test_homeassistant_energy_snapshot_functions_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def collect_homeassistant_energy_snapshot" in source
    assert "def persist_homeassistant_energy_snapshot" in source
    assert "def run_homeassistant_energy_snapshot" in source

def test_monthly_output_filenames_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"Enphase.csv"' in source
    assert '"Nordpool elektriciteit.csv"' in source
    assert '"NextEnergy actuele stroomprijs.csv"' in source

def test_scheduler_runs_homeassistant_energy_sampling():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "last_homeassistant_energy_run" in source
    assert "run_homeassistant_energy_snapshot()" in source
    assert "homeassistant_energy_sample_seconds" in source

def test_web_ui_has_homeassistant_energy_button():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Maak HA energiesnapshot" in source
    assert '"/homeassistant-energy-snapshot"' in source


def test_month_input_configuration_present():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert "month_input_enabled" in config
    assert "month_input_require_homewizard" in config
    assert "month_input_require_enphase" in config
    assert "month_input_require_nordpool" in config

def test_month_input_builder_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'MONTH_INPUT_ROOT = OUTPUT_ROOT / "01_Input"' in source
    assert "def build_month_input" in source
    assert "def write_deduplicated_csv" in source
    assert "month_input_validation.json" in source
    assert "month_input_manifest.json" in source

def test_enphase_is_normalized_to_kwh():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def transform_enphase_row" in source
    assert "value * 1000" in source
    assert 'row["unit"] = "kWh"' in source

def test_negative_zero_price_is_normalized():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def transform_price_row" in source
    assert 'row["value"] = "0.0"' in source

def test_expected_month_files_are_declared():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for filename in [
        "P1e.csv",
        "P1g.csv",
        "Airco Skt.csv",
        "Mobiel Skt.csv",
        "Heater kantoor Skt.csv",
        "Heater woonkamer Skt.csv",
        "Heater lounge Skt.csv",
        "Enphase.csv",
        "Nordpool elektriciteit.csv",
        "NextEnergy actuele stroomprijs.csv",
    ]:
        assert filename in source

def test_month_input_zip_and_ui_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "01_Input_{month_key}.zip" in source
    assert "Bouw maandmap" in source
    assert '"/build-month-input"' in source


def test_epex_configuration_present():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert "epex_electricity_output_name" in config
    assert "epex_gas_output_name" in config
    assert "epex_require_full_calendar_month" in config

def test_epex_csv_validation_functions_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def sniff_csv_rows" in source
    assert "def detect_timestamp_field" in source
    assert "def validate_epex_csv" in source
    assert "missing_dates" in source
    assert "duplicate_timestamps" in source

def test_epex_import_and_validation_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def run_epex_import_and_validate" in source
    assert '"EPEX stroom.csv"' in source
    assert '"EPEX gas.csv"' in source
    assert "EPEX_validation.json" in source

def test_epex_is_included_in_month_input():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'epex_root = OUTPUT_ROOT / "epex_monthdata" / month_key' in source
    assert 'epex_root / "EPEX stroom.csv"' in source
    assert 'epex_root / "EPEX gas.csv"' in source

def test_epex_ui_endpoint_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Importeer en valideer EPEX" in source
    assert '"/epex-import-validate"' in source


def test_share_mapping_and_transfer_config_present():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert "- share:rw" in config
    assert "transfer_enabled" in config
    assert "transfer_share_folder" in config
    assert "transfer_overwrite_existing" in config
    assert "transfer_require_valid_month" in config
    assert "transfer_notify_home_assistant" in config

def test_transfer_is_validation_gated():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def create_transfer_package" in source
    assert "validation_acceptable = (" in source
    assert 'validation.get("status") == "warning"' in source
    assert "Overdracht geblokkeerd" in source

def test_transfer_never_overwrites_by_default():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert "transfer_overwrite_existing: false" in config
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "overschrijven is uitgeschakeld" in source

def test_transfer_hash_verification_and_rollback_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def verify_transfer_copy" in source
    assert "hashlib.sha256" in source
    assert "Overdracht verificatie mislukt in staging." in source
    assert "ZIP-verificatie mislukt in staging." in source
    assert "backup.replace(destination)" in source

def test_home_assistant_notification_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "persistent_notification/create" in source
    assert "Energie maandimport gereed" in source

def test_transfer_ui_endpoint_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Maak overdrachtspakket" in source
    assert '"/create-transfer-package"' in source


def test_full_workflow_configuration_present():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert "full_workflow_enabled" in config
    assert "full_workflow_use_previous_month" in config
    assert "full_workflow_stop_on_error" in config
    assert "full_workflow_run_epex_when_enabled" in config

def test_full_workflow_function_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def run_full_month_workflow" in source
    assert "workflow_previous_month_key" in source
    assert "workflow_result.json" in source

def test_full_workflow_contains_all_major_steps():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for step in [
        "SlimmeMeterPortal API-test",
        "SlimmeMeterPortal maandimport",
        "HomeWizard detectie",
        "HomeWizard snapshot",
        "Home Assistant energiesnapshot",
        "EPEX import en validatie",
        "Maandmap bouwen",
        "Overdrachtspakket maken",
    ]:
        assert step in source

def test_full_workflow_stops_on_required_error():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "full_workflow_stop_on_error" in source
    assert "if required and options.full_workflow_stop_on_error" in source

def test_full_workflow_notifications_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Energie maandworkflow gereed" in source
    assert "Energie maandworkflow mislukt" in source

def test_full_workflow_ui_endpoint_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Verwerk maanddata" in source
    assert '"/run-full-month-workflow"' in source


def test_full_workflow_uses_existing_api_test_function():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def test_api()" in source
    assert "test_api_connection" not in source
    workflow_start = source.index("def run_full_month_workflow")
    workflow_end = source.index("def scheduler", workflow_start)
    workflow = source[workflow_start:workflow_end]
    assert '"SlimmeMeterPortal API-test"' in workflow
    assert "            test_api," in workflow

def test_full_workflow_direct_function_references_exist():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for function_name in [
        "test_api",
        "run_import",
        "discover_homewizard_devices",
        "run_homewizard_snapshot",
        "run_homeassistant_energy_snapshot",
        "run_epex_import_and_validate",
        "build_month_input",
        "create_transfer_package",
    ]:
        assert f"def {function_name}" in source


def test_manual_workflow_has_explicit_month_input():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '<input type="month" name="month"' in source
    assert "selected_month.replace" in source
    assert "collect_live_snapshots=True" in source

def test_historical_workflow_skips_live_snapshots():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "target_is_current_month" in source
    assert "Historische maand gebruikt reeds opgebouwde" in source
    assert "live_snapshots_collected" in source

def test_workflow_does_not_duplicate_error_steps():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "already_recorded = bool(" in source
    assert "if error_text not in errors:" in source


def test_warning_month_validation_is_accepted_without_required_gaps():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'month_status == "warning"' in source
    assert "and not missing_required" in source
    assert "and not empty_required" in source

def test_transfer_accepts_optional_warning_only():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "validation_acceptable = (" in source
    assert 'validation.get("status") == "warning"' in source
    assert '"month_validation_accepted": validation_acceptable' in source

def test_workflow_can_finish_with_warning():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'status = "failed" if errors else ("completed_warning" if warnings else "completed")' in source
    assert 'result.get("status") in {"completed", "completed_warning"}' in source
    assert 'if status in {"completed", "completed_warning"}:' in source


def test_full_workflow_refreshes_existing_transfer():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "replace_existing: bool = False" in source
    assert "create_transfer_package(month_key, replace_existing=True)" in source

def test_transfer_refresh_uses_staging_and_backup():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'staging = destination_root / f".{month_key}.staging"' in source
    assert 'backup = destination_root / f".{month_key}.backup"' in source
    assert "shutil.copytree(source, staging)" in source
    assert "verify_transfer_copy(source, staging)" in source
    assert "backup.replace(destination)" in source

def test_manual_transfer_remains_non_overwriting():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "allow_replace = bool(" in source
    assert "replace_existing or options.transfer_overwrite_existing" in source
    assert "Doelmap bestaat al en overschrijven is uitgeschakeld" in source

def test_transfer_manifest_records_replacement():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"existing_destination_replaced": bool(replace_existing)' in source


def test_v510_source_aware_validation_profiles():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "VALIDATION_PROFILES" in source
    assert '"slimmemeterportal"' in source
    assert '"expected_records_per_day": {1}' in source
    assert 'expected_count(kind, current, "slimmemeterportal")' in source

def test_v510_smp_daily_records_are_not_quarter_hour_expected():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    block_start = source.index("VALIDATION_PROFILES")
    block_end = source.index("def safe", block_start)
    block = source[block_start:block_end]
    smp = block[block.index('"slimmemeterportal"'):block.index('"homewizard"')]
    assert "{96" not in smp
    assert '"expected_records_per_day": {1}' in smp

def test_v510_status_names_are_production_friendly():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"completed_warning"' in source
    assert '"failed"' in source
    assert '"completed_with_warnings"' not in source
    assert '"completed_with_errors"' not in source


def test_v520_month_input_optional_missing_is_info():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'status = "completed"' in source
    assert 'status = "completed_info"' in source
    assert 'status = "failed"' in source

def test_v520_workflow_has_separate_infos():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "infos: list[str] = []" in source
    assert '"infos": infos' in source
    assert 'infos.append("EPEX is nog niet geconfigureerd.")' in source

def test_v520_consistent_workflow_statuses():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"completed_warning"' in source
    assert '"completed_info"' in source
    assert 'status = "failed" if errors else ("completed_warning" if warnings else "completed")' in source

def test_v520_epex_default_is_not_configured():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"epex_last_validation_status": "not_configured"' in source


def test_v530_month_info_only_when_real_info_exists():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "info_messages: list[str] = []" in source
    assert "elif info_messages:" in source
    assert '"infos": info_messages' in source

def test_v530_epex_disabled_is_not_configured():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'results["status"] = "not_configured"' in source
    assert '"reason": f"{source_name} is uitgeschakeld."' in source

def test_v530_technical_status_normalization_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def normalize_technical_status" in source
    assert 'normalized["epex_last_validation_status"] = "not_configured"' in source
    assert 'normalized["month_input_last_status"] = "completed"' in source


def test_v540_persists_normalized_status():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def persist_normalized_status" in source
    assert "update_state(**changes)" in source
    assert "persist_normalized_status(Options.load())" in source

def test_v540_resets_disabled_epex_during_workflow():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'epex_last_validation_status="not_configured"' in source
    assert "persist_normalized_status(options)" in source

def test_v540_keeps_completed_month_status():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'normalized["month_input_last_status"] = "completed"' in source


def test_v550_expected_files_are_configuration_aware():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def expected_month_input_files(options: Options)" in source
    assert 'if options.epex_electricity_enabled:' in source
    assert 'if options.epex_gas_enabled:' in source
    assert '"expected_files": expected_month_input_files(options)' in source

def test_v550_disabled_epex_not_added_to_source_map():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'source_map.append(' in source
    assert '(epex_root / "EPEX stroom.csv", target / "EPEX stroom.csv", None)' in source
    assert '(epex_root / "EPEX gas.csv", target / "EPEX gas.csv", None)' in source

def test_v550_old_epex_info_is_normalized():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "disabled_epex_info = all(" in source
    assert 'normalized["month_input_last_status"] = "completed"' in source


def test_v600_report_handoff_builder_exists():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def create_report_handoff" in source
    assert '"schema": "energie_report_handoff_v1"' in source
    assert '"report_request.json"' in source
    assert '"report_request_manifest.json"' in source

def test_v600_official_generators_are_in_handoff():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Energierapport_Pagina1_Echte_Generator_v7" in source
    assert "Energierapport_Pagina2_Generator_v6.0" in source
    assert "Energierapport_Pagina3_tm_13_Generator_v1.0" in source

def test_v600_transfer_creates_report_handoff():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "report_handoff = create_report_handoff(" in source
    assert 'transfer_manifest["report_handoff"] = report_handoff' in source
    assert 'name="Rapportoverdracht voorbereiden"' in source

def test_v600_state_tracks_report_handoff():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"report_handoff_last_status": None' in source
    assert 'report_handoff_last_status="ready"' in source


def test_v610_report_handoff_loader_and_validator():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def load_report_handoff" in source
    assert "def validate_report_handoff_files" in source
    assert 'payload.get("schema") != "energie_report_handoff_v1"' in source
    assert "Officiële generatorconfiguratie wijkt af." in source

def test_v610_report_generation_runner():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def run_report_generation_from_handoff" in source
    assert 'report_generation_last_status="running"' in source
    assert '"status": "ready"' in source
    assert '"status": "completed" if trigger_result.get("status") == "ok" else "failed"' in source

def test_v610_workflow_runs_report_coupling():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"Rapportgenerator koppelen"' in source
    assert "run_report_generation_from_handoff(" in source
    assert "required=(options.report_service_enabled or options.report_trigger_enabled)" in source

def test_v610_report_status_endpoints():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"/report-generation-status"' in source
    assert '"/run-report-generation"' in source
    assert "Genereer compleet maandrapport" in source


def test_v620_report_service_options_exist():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert "report_service_enabled: bool" in source
    assert 'report_service_root: "Energie_Rapportservice"' in config
    assert 'report_service_timeout_seconds: "int(60,3600)"' in config

def test_v620_report_service_scaffold():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def report_service_paths" in source
    assert "def initialize_report_service" in source
    assert "def discover_report_generators" in source
    assert '"waiting_for_generators"' in source
    assert '"service_contract.json"' in source

def test_v620_local_generator_execution():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def execute_local_report_service" in source
    assert "subprocess.run(" in source
    assert '"--request"' in source
    assert '"--input"' in source
    assert '"--output"' in source

def test_v620_output_validation():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def validate_report_outputs" in source
    assert "Definitief rapport ontbreekt of is leeg" in source
    assert "Recovery Update ontbreekt of is leeg" in source


def test_v630_page1_state_and_executor():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"report_page1_last_status": None' in source
    assert "def execute_page1_generator" in source
    assert '"waiting_for_page_1"' in source
    assert 'f"Energierapport_Pagina1_{month_key}.pdf"' in source

def test_v630_discovery_has_page1_ready():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"page_1_ready"' in source
    assert '"role_status": role_status' in source
    assert 'role_status["page_1"] == "ready"' in source

def test_v630_page1_endpoint_and_button():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"/run-report-page1"' in source
    assert "Test rapportgenerator pagina 1" in source
    assert '"page_1_result.json"' in source

def test_v630_staged_local_service():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"page_1_completed"' in source
    assert "Pagina 1 is uitgevoerd; pagina 2 en pagina 3-13 ontbreken nog." in source


def test_v640_bundled_generators_present():
    root = ADDON / "rootfs/app/report_generators"
    assert (root / "Energierapport_Pagina1_Echte_Generator_v7").is_dir()
    assert (root / "Energierapport_Pagina2_Generator_v6_0").is_dir()
    assert (root / "Energierapport_Pagina3_tm_13_Generator_v1_0").is_dir()

def test_v640_installer_and_wrappers():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def install_bundled_report_generators" in source
    assert "def generator_wrapper_source" in source
    assert '"packages"' in source
    assert '"data"' in source
    assert "Installeer officiële rapportgeneratoren" in source

def test_v640_exact_official_wrapper_names():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'wrapper = paths["generators"] / f"{official_name}.py"' in source
    assert "GENERATOR_BUNDLE_FOLDERS" in source

def test_v640_reportlab_runtime_dependency():
    dockerfile = (ADDON / "Dockerfile").read_text(encoding="utf-8")
    assert "py3-reportlab" in dockerfile


def test_v650_report_adapter_exists():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def build_report_adapter_data" in source
    assert "def cumulative_delta" in source
    assert '"page_1.json"' in source
    assert '"page_2.json"' in source
    assert '"pages_3_13.json"' in source

def test_v650_pdf_merge_exists():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def merge_report_pdfs" in source
    assert "from pypdf import PdfReader, PdfWriter" in source
    assert '"merge_result.json"' in source

def test_v650_service_runs_adapter_and_merge():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "adapter = build_report_adapter_data(options, handoff)" in source
    assert "merge = merge_report_pdfs(handoff, work_folder)" in source
    assert "create_recovery_update(options, handoff, work_folder)" in source

def test_v650_runtime_has_pypdf():
    dockerfile = (ADDON / "Dockerfile").read_text(encoding="utf-8")
    assert "py3-pypdf" in dockerfile


def test_v660_report_service_enabled_by_default():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert 'raw.get("report_service_enabled", True)' in source
    assert "report_service_enabled: true" in config

def test_v660_real_recovery_update_scope():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def create_recovery_update" in source
    assert '"scope": ["03_Systeem/", "04_Scripts/"]' in source
    assert "04_Scripts/Rapportgeneratoren/packages/" in source
    assert "create_recovery_update_placeholder" not in source

def test_v660_publishes_exact_month_output():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def publish_month_output" in source
    assert 'transfer_folder.parent / "02_Output" / month_key' in source
    assert '"output_manifest.json"' in source
    assert "sha256_file(source) != sha256_file(destination)" in source

def test_v660_local_service_requires_publication_success():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "publication = publish_month_output(handoff, work_folder)" in source
    assert 'publication["status"] == "completed"' in source
    assert '"publication": publication' in source
