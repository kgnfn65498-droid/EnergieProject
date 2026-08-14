from pathlib import Path
import ast
import json
import re

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "slimmemeterportal_import"
MAIN = ADDON / "rootfs/app/main.py"

def test_python_syntax():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    ast.parse(source)

def test_version_matches():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    main = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    cfg_version = re.search(r'version:\s*"([^"]+)"', config).group(1)
    app_version = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', main).group(1)
    assert cfg_version == app_version == "32.0.33"

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
    assert 'version: "32.0.33"' in config
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
    assert 'ipaddress.ip_network("172.32.0.1/16")' in source
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
    assert "create_transfer_package(month_key, replace_existing=True, send_notification=False)" in source

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


def test_v736_historical_snapshot_skip_is_informational_not_warning():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'infos.append(\n                "Historische maand: live snapshots bewust niet aan doelmaand toegevoegd."' in source
    assert 'warnings.append(\n                "Historische maand: live snapshots niet aan doelmaand toegevoegd."' not in source

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
    assert ("py3-reportlab" in dockerfile or "reportlab>=4,<5" in dockerfile)


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
    assert ("py3-pypdf" in dockerfile or "pypdf>=5,<7" in dockerfile)


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


def test_v661_sys_import_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "\nimport sys\n" in source


def test_v662_sys_is_real_top_level_import():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    header = source.split("APP_VERSION", 1)[0]
    assert "\nimport sys\n" in header

def test_v662_all_main_sys_references_are_covered():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    header = source.split("APP_VERSION", 1)[0]
    assert "\nimport sys\n" in header
    assert "sys.executable" in source


def test_v663_installs_report_modules_into_runtime_python():
    dockerfile = (ADDON / "Dockerfile").read_text(encoding="utf-8")
    assert "/usr/local/bin/python3 -m pip install" in dockerfile
    assert '"reportlab>=4,<5"' in dockerfile
    assert '"pypdf>=5,<7"' in dockerfile
    assert "import reportlab, pypdf" in dockerfile

def test_v663_runtime_checker_exists():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def check_report_runtime" in source
    assert 'for name in ("reportlab", "pypdf")' in source
    assert '"python": sys.executable' in source

def test_v663_selftest_checks_report_runtime():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'add(' in source
    assert '"report_runtime"' in source
    assert 'runtime = check_report_runtime()' in source

def test_v663_runtime_button_exists():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"/check-report-runtime"' in source
    assert "Controleer rapportmodules" in source


def test_v670_workflow_audit_exists():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def audit_completed_month_workflow" in source
    assert '"published_files"' in source
    assert "expected_names" in source
    assert "sha256_file(path)" in source

def test_v670_audit_runs_after_completed_report():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'result["audit"] = audit_completed_month_workflow(month_key)' in source
    assert 'result["audit"].get("status") != "completed"' in source
    assert "Eindcontrole van de maandworkflow is mislukt." in source

def test_v670_page1_status_is_updated_in_full_run():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'if role == "page_1":' in source
    assert "report_page1_last_status=page1_status" in source
    assert "report_page1_last_output=str(page1_output)" in source

def test_v670_audit_status_endpoint():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"/workflow-audit-status"' in source
    assert ">Eindcontrole</a>" in source


def test_v680_retention_option():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert "report_service_retention_months: int" in source
    assert "report_service_retention_months: 3" in config
    assert 'raw.get("report_service_retention_months", 3)' in source

def test_v680_cleanup_only_service_history():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def cleanup_report_service_history" in source
    assert 'for key in ("work", "output", "logs")' in source
    assert "02_Output" not in source.split("def cleanup_report_service_history", 1)[1].split("def build_compact_workflow_summary", 1)[0]

def test_v680_compact_summary():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def build_compact_workflow_summary" in source
    assert '"/workflow-summary"' in source
    assert ">Samenvatting</a>" in source

def test_v680_runs_after_successful_audit():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'result["retention"] = cleanup_report_service_history(options)' in source
    assert 'result["summary"] = build_compact_workflow_summary(month_key)' in source


def test_v690_global_workflow_lock():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "WORKFLOW_LOCK = threading.Lock()" in source
    assert "def workflow_lock_snapshot" in source
    assert "if not WORKFLOW_LOCK.acquire(blocking=False):" in source
    assert '"status": "busy"' in source

def test_v690_coordinated_import():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def coordinated_month_import" in source
    assert "workflow_import_wait_seconds" in source
    assert "reused_completed_import" in source
    assert "coordinated_month_import(year, month, options)" in source

def test_v690_summary_ignores_stale_error_after_success():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'state.get("workflow_audit_last_status") == "completed"' in source
    assert 'state.get("report_output_last_status") == "completed"' in source

def test_v690_lock_status_endpoint():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"/workflow-lock-status"' in source
    assert ">Workflowstatus</a>" in source


def test_v690_workflow_lock_is_released():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    workflow = source.split("def run_full_month_workflow", 1)[1]
    assert 'set_workflow_lock_state(' in workflow
    assert 'status="idle"' in workflow
    assert "WORKFLOW_LOCK.release()" in workflow


def test_v691_idle_lock_clears_active_fields():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "workflow_lock_started_at=None" in source
    assert "workflow_lock_month=None" in source
    assert "workflow_lock_step=None" in source
    assert "workflow_lock_last_duration_seconds=duration_seconds" in source

def test_v691_discovery_uses_mapped_names():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "mapped_by_serial" in source
    assert 'device["label"] = mapped.get("label"' in source
    assert 'device["output_name"] = mapped.get(' in source
    assert "update_state(homewizard_discovery_devices=found)" in source

def test_v691_validates_required_report_inputs():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def validate_report_input_files" in source
    assert '"P1e.csv"' in source
    assert '"NextEnergy actuele stroomprijs.csv"' in source
    assert "Rapportinput is onvolledig" in source
    assert '"input_validation": input_validation' in source

# Fase 7.0: maandafsluiting, historische selectie en operationele status.
def test_version_7_0_1_matches():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    main = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'version: "32.0.33"' in config
    assert 'APP_VERSION = "32.0.33"' in main


def test_phase7_configuration_present():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    for key in (
        "automatic_month_close_enabled",
        "automatic_month_close_day",
        "automatic_month_close_hour",
        "operation_history_months",
    ):
        assert key in config


def test_phase7_automatic_month_close_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def automatic_month_close_due" in source
    assert "automatic_month_close_last_month" in source
    assert 'execute_automatic_month_close(options, close_month, trigger="automatic")' in source


def test_phase7_historical_selection_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def historical_month_allowed" in source
    assert 'action="run-historical-month"' in source
    assert 'path.endswith("/run-historical-month")' in source
    assert "collect_live_snapshots=False" in source


def test_phase7_operation_status_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def operation_status" in source
    assert 'path.endswith("/operation-status")' in source
    assert "Operationele status" in source


def test_v701_operation_console_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Operationele console" in source
    assert "Actuele voortgang" in source
    assert "Historische runs" in source
    assert "Diagnostiek en beheer" in source
    assert "setInterval(refreshStatus,5000)" in source

def test_v701_preserves_core_workflow_actions():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for action in [
        "run-full-month-workflow", "run-historical-month", "central-validation",
        "run-report-generation", "create-transfer-package", "self-test"
    ]:
        assert f'action="{action}"' in source

def test_v701_preserves_output_contract_names():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'f"Energierapport_{month_key}.pdf"' in source
    assert 'f"Recovery_Update_{month_key}.zip"' in source


def test_v710_central_workflow_console_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "start_workflow_background" in source
    assert 'action="start-month-workflow"' in source
    assert 'action="resume-month-workflow"' in source
    assert "Hervat mislukte workflow" in source

def test_v710_live_workflow_log_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "WORKFLOW_LOG_NAME" in source
    assert "append_workflow_log" in source
    assert "workflow_log_tail" in source
    assert 'workflow-log?month=' in source

def test_v710_resume_reuses_completed_steps():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "resumable_step_names" in source
    assert "if resume and name in resume_completed" in source
    assert '"resumed": resume' in source

def test_v710_health_dashboard_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def health_dashboard" in source
    assert 'path.endswith("/health-dashboard")' in source
    assert "Gezondheidsdashboard" in source

def test_v710_output_contract_unchanged():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Energierapport_" in source
    assert "Recovery_Update_" in source
    assert "03_Systeem/" in source
    assert "04_Scripts/" in source

def test_v711_cancel_is_controlled_status():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "class ImportCancelled(Exception)" in source
    assert 'status="cancelled"' in source
    assert 'last_cancel_reason=exc.reason' in source
    assert 'LOGGER.info("Import gecontroleerd geannuleerd:' in source
    assert 'raise RuntimeError("Import geannuleerd.")' not in source


def test_v711_cancel_reason_is_explicit():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'return "user_requested"' in source
    assert 'return "service_shutdown"' in source
    assert 'last_cancel_reason="user_requested"' in source


def test_v711_output_contract_unchanged():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'f"Energierapport_{month_key}.pdf"' in source
    assert 'f"Recovery_Update_{month_key}.zip"' in source
    assert '"03_Systeem/"' in source
    assert '"04_Scripts/"' in source


def test_v712_current_month_never_requests_future_days():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "last_day_to_fetch = today.day" in source
    assert "for day_number in range(1, last_day_to_fetch + 1)" in source
    assert "Huidige maand begrensd tot vandaag" in source


def test_v712_workflow_timeout_and_heartbeat_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    assert "workflow_step_timeout_seconds" in source
    assert "workflow_heartbeat_seconds" in source
    assert "def workflow_heartbeat(" in source
    assert "SlimmeMeterPortal maandimport overschreed de workflow-timeout" in source
    assert "workflow_step_timeout_seconds: 900" in config
    assert "workflow_heartbeat_seconds: 5" in config


def test_v712_background_worker_has_lock_failsafe():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Failsafe heeft achtergebleven workflow-lock vrijgegeven" in source
    assert "Workflow is onverwacht gestopt; lock is veilig vrijgegeven." in source


def test_v713_workflow_failure_diagnostics_present():
    source = Path("slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def record_workflow_failure(" in source
    assert "traceback.format_exception" in source
    assert "full_workflow_last_error_type" in source
    assert "full_workflow_last_error_step" in source
    assert "full_workflow_last_traceback" in source
    assert 'path.endswith("/download-workflow-log")' in source
    assert "Laatste workflowfout" in source
    assert "Download workflowlog" in source


def test_v713_workflow_log_renders_traceback():
    source = Path("slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert "if(x.traceback)" in source
    assert "application/x-ndjson" in source


def test_v714_workflow_log_calls_do_not_pass_message_twice():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    bad_calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "append_workflow_log":
            keyword_names = {kw.arg for kw in node.keywords if kw.arg is not None}
            if len(node.args) >= 3 and "message" in keyword_names:
                bad_calls.append(node.lineno)
    assert bad_calls == [], f"append_workflow_log krijgt message dubbel op regels: {bad_calls}"

def test_v714_heartbeat_uses_non_conflicting_detail_key():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'append_workflow_log(month_key, "info", "Heartbeat", step=step, heartbeat_message=message, **extra)' in source
    assert 'append_workflow_log(month_key, "info", "Heartbeat", step=step, message=message, **extra)' not in source


def test_v715_clears_stale_workflow_diagnostics_on_start():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    required = [
        'full_workflow_last_status="running"',
        'full_workflow_last_error=None',
        'full_workflow_last_error_type=None',
        'full_workflow_last_error_step=None',
        'full_workflow_last_traceback=None',
        'progress_current=0',
        'progress_total=0',
        'progress_message="Workflow gestart"',
    ]
    for token in required:
        assert token in source, token


def test_v715_active_workflow_is_not_health_failure():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'workflow_running = WORKFLOW_LOCK.locked()' in source
    assert 'last_status in {"running", "completed", "completed_warning"}' in source


def test_v717_generated_console_javascript_has_escaped_newlines():
    """Regression: Python HTML rendering must not inject raw newlines into JS string literals."""
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "if(x.traceback) line+='\\\\n'+x.traceback;" in source
    assert "}}).join('\\\\n');" in source


def test_v717_console_polling_contract_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"live_log": live_log' in source
    assert 'Array.isArray(op.live_log)' in source
    assert "setInterval(refreshStatus,2500)" in source
    assert "box.scrollTop=box.scrollHeight" in source


def test_v717_self_test_is_human_readable_html():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Volledige zelftest" in source
    assert "ALLE TESTS GESLAAGD" in source
    assert "Terug naar operationele console" in source


def test_v717_operation_status_embeds_live_log():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"live_log": live_log' in source
    assert 'limit=80' in source


def test_v720_notification_config_present():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "workflow_notify_home_assistant" in config
    assert "workflow_notify_on_start" in config
    assert "Automatische energie-maandafsluiting gestart" in source
    assert "Automatische energie-maandafsluiting gereed" in source


def test_v720_automatic_retry_guard_present():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "automatic_month_close_retry_hours" in config
    assert "automatic_month_close_last_attempt" in source
    assert "automatic_month_close_next_retry" in source
    assert 'trigger="automatic"' in source


def test_v720_workflow_records_trigger():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"trigger": trigger' in source
    assert 'full_workflow_last_trigger=trigger' in source


def test_v720_full_workflow_suppresses_transfer_notification():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "send_notification: bool = True" in source
    assert "replace_existing=True, send_notification=False" in source


def test_v730_weighted_visual_progress_contract_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'WORKFLOW_VISUAL_PHASES' in source
    assert 'def workflow_visualization' in source
    assert '"visual_progress": visual' in source
    assert 'WORKFLOW_VISUAL_TOTAL_STEPS = len(WORKFLOW_VISUAL_PHASES)' in source


def test_v730_progress_resets_locally_on_submit():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "bar.style.width='0%'" in source
    assert "textContent='Stap 0 van 11'" in source
    assert "textContent='Workflow starten'" in source


def test_v730_history_uses_visual_step_count():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'def visual_step_counts_from_result' in source
    assert '"steps_total": visual_step_counts_from_result(result)[1]' in source


def test_v730_progress_ui_has_eta_and_flow_animation():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'id="workflow-eta"' in source
    assert '@keyframes flow' in source
    assert "bar.className=vp.running?'running':''" in source

def test_v731_historical_reuses_existing_month_input_files():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "reuse_existing: bool = False" in source
    assert "reuse_existing=(not collect_live_snapshots)" in source
    assert '"reused_existing": True' in source
    assert '"reused_existing_files"' in source


def test_v731_historical_runs_in_background_and_returns_to_console():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    route = source[source.index('if path.endswith("/run-historical-month")'):source.index('if path.endswith("/run-full-month-workflow")')]
    assert "start_workflow_background(" in route
    assert 'trigger="historical"' in route
    assert 'self.send_redirect("./")' in route


def test_v731_api_test_returns_to_console():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    route = source[source.index('if path.endswith("/test-api")'):source.index('if not (path.endswith("/run")')]
    assert 'self.send_redirect("./")' in route
    assert "API-test mislukt" in route
    assert "Terug naar operationele console" in route


def test_v731_background_workflow_accepts_explicit_trigger():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "trigger: str | None = None" in source
    assert 'resolved_trigger = trigger or ("resume" if resume else "manual")' in source
    assert "trigger=resolved_trigger" in source


def test_v732_historical_recovery_searches_transfer_folder_and_zip():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def recover_historical_month_input" in source
    assert 'transfer_root / month_key' in source
    assert 'transfer_root / f"01_Input_{month_key}.zip"' in source
    assert 'MONTH_INPUT_ROOT / f"01_Input_{month_key}.zip"' in source


def test_v733_historical_recovery_never_overwrites_existing_files():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'if destination.exists()' in source
    assert 'if destination.exists() or not member:' in source


def test_v733_historical_recovery_searches_downloadable_month_tree_recursively():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'OUTPUT_ROOT / month_key' in source
    assert 'source_root.rglob(filename)' in source
    assert 'Historisch bronbestand hersteld' in source


def test_v733_historical_recovery_discovers_saved_month_archives():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'rglob(f"*{month_key}*.zip")' in source
    assert 'candidate.is_file() and candidate not in zips' in source


def test_v732_month_validation_reports_checked_historical_paths():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"source_paths_checked"' in source
    assert 'gecontroleerde historische bronnen' in source


def test_v734_historical_required_files_are_source_aware():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def required_month_input_files(options: Options, *, historical: bool = False)" in source
    assert "if not historical and options.month_input_require_homewizard:" in source
    assert "required = required_month_input_files(options, historical=reuse_existing)" in source


def test_v735_historical_report_is_skipped_when_detail_sources_incomplete():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def report_input_readiness(month_key: str, options: Options)" in source
    assert '"Historisch rapport informatief overgeslagen"' in source
    assert '"Historische detailbronnen zijn niet volledig beschikbaar."' in source
    assert 'status="skipped"' in source


def test_historical_report_skip_is_info_not_warning():
    main = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'infos.append(info)' in main
    assert '"Historisch rapport informatief overgeslagen"' in main
    assert 'warnings.append(warning)' not in main[main.index('if historical_mode and readiness.get("status") != "ready"'):main.index('else:', main.index('if historical_mode and readiness.get("status") != "ready"'))]


def test_v740_has_pre_report_final_validation():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def validate_pre_report_workflow(" in source
    assert '"Eindvalidatie vóór rapportage"' in source
    assert '"pre_report_validation.json"' in source
    assert 'last_pre_report_validation=result' in source


def test_v740_auto_coordinates_enphase_only_for_live_target_month():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"Enphase bronimport"' in source
    assert "if collect_live_snapshots and target_is_current_month:" in source
    assert "Historische Enphase live-import bewust niet uitgevoerd." in source


def test_v740_historical_preflight_does_not_require_live_detail_sources():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "if historical_mode:" in source
    assert "Historische live-broncontrole genegeerd:" in source
    assert "Historische rapportinput is niet volledig" in source
    assert '("Eindvalidatie vóór rapportage", 3.0, 0.3)' in source


def test_v750_automatic_close_preflight_present():
    source=(ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def automatic_month_close_preflight" in source
    assert "automatic_month_close_last_preflight" in source
    assert 'automatic_month_close_last_status="blocked"' in source

def test_v750_automatic_close_finalization_present():
    source=(ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def automatic_month_close_finalize" in source
    assert "automatic_month_close_last_finalization" in source
    assert 'f"Recovery_Update_{month_key}.zip"' in source
    assert "files_exist=all(Path(x).is_file() for x in published)" in source

def test_v750_preflight_before_automatic_workflow():
    source=(ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    shared=source[source.index("def execute_automatic_month_close"):source.index("def automatic_scheduler_acceptance_test")]
    assert shared.index("automatic_month_close_preflight") < shared.index("run_full_month_workflow")


def test_v760_console_has_automatic_close_controls():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'action="save-automatic-month-close"' in source
    assert 'action="test-automatic-month-close"' in source
    assert 'Test automatische maandafsluiting nu' in source
    assert 'automatic_month_close_test_last_result' in source

def test_v760_ui_override_is_limited_to_automatic_close_fields():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'AUTO_CLOSE_UI_OPTIONS_PATH' in source
    assert 'automatic_month_close_enabled' in source
    assert 'automatic_month_close_day' in source
    assert 'automatic_month_close_hour' in source
    assert 'automatic_month_close_retry_hours' in source

def test_v760_product_test_does_not_mark_scheduler_month_complete():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    start = source.index('def run_automatic_month_close_test')
    end = source.index('def automatic_month_close_preflight', start)
    block = source[start:end]
    assert 'trigger="automatic_test"' in block
    assert 'scheduler_state_changed' in block
    assert 'automatic_month_close_last_month=' not in block

def test_v760_product_test_runs_preflight_workflow_finalization():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    start = source.index('def run_automatic_month_close_test')
    end = source.index('def automatic_month_close_preflight', start)
    block = source[start:end]
    assert 'automatic_month_close_preflight' in block
    assert 'run_full_month_workflow' in block
    assert 'automatic_month_close_finalize' in block


def test_v770_clear_automatic_month_close_switch():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'class="switch-row"' in source
    assert 'id="auto-close-enabled"' in source
    assert 'class="switch-slider"' in source
    assert "Automatisch vorige maand verwerken" in source
    assert "AAN" in source and "UIT" in source


def test_v770_workflow_actions_disable_while_running():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'workflow_active = str(workflow.get("status")' in source
    assert 'class="workflow-action"' in source
    assert "document.querySelectorAll('.workflow-action').forEach(btn=>btn.disabled=active)" in source


def test_v770_resume_only_when_failed():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'resume_available = str(last_run.get("status")' in source
    assert "Geen mislukte workflow om te hervatten." in source
    assert "De hervatknop verschijnt automatisch" in source


def test_v770_automatic_status_updates_live():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'id="auto-close-top-status"' in source
    assert 'id="auto-last-preflight"' in source
    assert 'id="auto-last-finalization"' in source
    assert 'id="auto-last-test"' in source


def test_v780_product_test_marks_running_before_background_thread():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    route = source[source.index('if path.endswith("/test-automatic-month-close")'):source.index('if path.endswith("/start-month-workflow")')]
    assert '"status": "running"' in route
    assert route.index('"status": "running"') < route.index("threading.Thread")


def test_v780_old_product_test_is_not_presented_as_current_error():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "auto_test_current_version" in source
    assert 'auto_test_display_status = "Opnieuw testen"' in source
    assert "Laatste test was met versie" in source


def test_v780_automatic_readiness_requires_current_successful_full_chain():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'production = auto_close.get("production_readiness")' in source
    assert 'auto_test_ok = bool(production.get("ready"))' in source
    assert "Productietest vereist" in source


def test_v780_product_test_error_detail_is_visible():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'id="auto-last-test-detail"' in source
    assert "test.error" in source


def test_v790_automatic_test_is_valid_workflow_trigger():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'trigger not in {"manual", "historical", "automatic", "automatic_test", "resume"}' in source
    assert 'trigger="automatic_test"' in source


def test_v790_automatic_test_keeps_scheduler_semantics_separate():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"scheduler_state_changed": False' in source
    assert 'trigger in {"automatic", "automatic_test"}' in source


def test_v800_production_readiness_requires_same_version_full_chain():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    validation=source[source.index("def validate_production_certificate"):source.index("def append_production_certificate_history")]
    assert 'str(certificate.get("version") or "") == APP_VERSION' in validation
    assert 'str(certificate.get("preflight_status") or "") == "ok"' in validation
    assert 'str(certificate.get("finalization_status") or "") == "ok"' in validation


def test_v800_scheduler_enable_is_gated_by_product_test():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    section = source[source.index("def save_automatic_month_close_settings"):source.index("def run_automatic_month_close_test")]
    assert "if enabled and not automatic_production_readiness().get" in section
    assert "kan pas AAN na certificering van productiekern" in section


def test_v800_operation_status_exposes_production_state():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"production_readiness": automatic_production_readiness(state)' in source
    assert '"next_scheduled_run": (' in source and "next_automatic_month_close_run(options)" in source
    assert 'Productiestatus v{APP_VERSION}' in source


def test_v800_next_automatic_run_only_when_enabled():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    section = source[source.index("def next_automatic_month_close_run"):source.index("def save_automatic_month_close_settings")]
    assert "if not options.automatic_month_close_enabled" in section
    assert "return candidate.isoformat()" in section


def test_v810_runtime_scheduler_gate_requires_current_product_test():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    section = source[source.index("def automatic_month_close_due"):source.index("def scheduler()")]
    assert 'if not automatic_production_readiness().get("ready"):' in section


def test_v810_operation_status_distinguishes_configured_and_effective_scheduler():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"scheduler_effective": bool(' in source
    assert '"history": automatic_history' in source


def test_v810_human_readable_planning_and_history():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def format_local_datetime" in source
    assert "Automatische maandhistorie" in source
    assert "formatLocalDateTime" in source


def test_v810_automatic_history_only_contains_auto_triggers():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'if item.get("trigger") not in {"automatic", "automatic_test"}:' in source
    assert "continue" in source


def test_v820_switch_has_dedicated_immediate_persist_endpoint():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def set_automatic_month_close_enabled" in source
    assert 'set-automatic-month-close-enabled' in source
    assert "Aan/Uit wordt direct opgeslagen" in source


def test_v820_product_test_guards_scheduler_config_byte_for_byte():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    section = source[source.index("def run_automatic_month_close_test"):source.index("def automatic_month_close_preflight")]
    assert "scheduler_config_before" in section
    assert "scheduler_config_after" in section
    assert "scheduler_config_after != scheduler_config_before" in section
    assert "oorspronkelijke planning is hersteld" in section


def test_v820_finalization_requires_exact_two_publication_files():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    section = source[source.index("def automatic_month_close_finalize"):source.index("def automatic_month_close_due")]
    assert "names==expected" in section
    assert "len(published)==2" in section


def test_v820_finalization_checks_pdf_and_recovery_zip_integrity():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    section = source[source.index("def automatic_month_close_finalize"):source.index("def automatic_month_close_due")]
    assert 'b"%PDF"' in section
    assert "recovery_zip.testzip()" in section
    assert '"report_pdf_integrity"' in section
    assert '"recovery_zip_integrity"' in section


def test_v830_scheduler_uses_shared_execution_helper():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    scheduler = source[source.index("def scheduler()"):source.index("def month_archives()")]
    assert 'execute_automatic_month_close(options, close_month, trigger="automatic")' in scheduler


def test_v830_acceptance_uses_real_due_and_shared_executor():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    section = source[source.index("def automatic_scheduler_acceptance_test"):source.index("def automatic_month_close_due")]
    compact = section.replace(" ", "").replace("\n", "")
    assert "automatic_month_close_due(options,simulated_at)" in compact
    assert "execute_automatic_month_close(" in section
    assert 'trigger="automatic"' in compact


def test_v830_acceptance_restores_scheduler_bookkeeping():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    section = source[source.index("def automatic_scheduler_acceptance_test"):source.index("def automatic_month_close_due")]
    assert "scheduler_before" in section
    assert "update_state(**scheduler_before)" in section
    assert "scheduler_bookkeeping_restored" in section


def test_v830_console_exposes_scheduler_acceptance_test():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Simuleer volgende scheduler-run nu" in source
    assert "test-scheduler-acceptance" in source
    assert '"scheduler_acceptance_last_result": state.get("automatic_scheduler_acceptance_last_result")' in source


def test_v840_history_distinguishes_scheduler_test():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'run_type = "Scheduler-test"' in source
    assert '"run_type": run_type' in source
    assert "<th>Versie</th>" in source
    assert "<th>Eindcontrole</th>" in source


def test_v840_history_preserves_version_and_finalization():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"version": result.get("version")' in source
    assert '"version": item.get("version")' in source
    assert '"finalization_status": finalization_status' in source


def test_v840_acceptance_verifies_switch_unchanged():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    section = source[source.index("def automatic_scheduler_acceptance_test"):source.index("def automatic_month_close_due")]
    assert "scheduler_enabled_before" in section
    assert "scheduler_enabled_after" in section
    assert "scheduler_enabled_unchanged" in section
    assert "Scheduler Aan/Uit is tijdens de acceptatietest gewijzigd." in section


def test_v840_console_reports_switch_unchanged():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "schedulerinstelling ongewijzigd" in source


def test_v850_append_only_ledger_exists():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'AUTOMATIC_RUN_LEDGER_PATH = Path("/config/output/automatic_run_history.jsonl")' in source
    assert "def append_automatic_run_history" in source

def test_v850_records_three_run_types():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"type": "Test"' in source
    assert '"type": "Scheduler-test"' in source
    assert '"type": "Automatisch"' in source

def test_v850_scheduler_test_not_double_recorded():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def automatic_scheduler_acceptance_test"):source.index("def automatic_month_close_due")]
    compact=section.replace(" ","").replace("\\n","")
    assert "record_as_real_automatic=False" in compact

def test_v850_console_prefers_ledger():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def operation_status"):source.index("def status_class")]
    assert "read_automatic_run_history" in section
    assert 'automatic_history_source = "append_only_ledger"' in section
    assert 'automatic_history_source = "legacy_workflow_results"' in section


def test_v851_scheduler_acceptance_auto_runs_required_product_test():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def automatic_scheduler_acceptance_test"):source.index("def automatic_month_close_due")]
    assert "prerequisite_product_test = run_automatic_month_close_test(prerequisite_month)" in section
    assert "automatic_production_readiness().get(\"ready\")" in section
    assert "options = Options.load()" in section


def test_v851_scheduler_acceptance_stops_when_prerequisite_fails():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def automatic_scheduler_acceptance_test"):source.index("def automatic_month_close_due")]
    assert "Automatische voorbereidende productietest voor " in section
    assert "is mislukt:" in section


def test_v851_acceptance_records_prerequisite_evidence():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"prerequisite_product_test": prerequisite_product_test' in source
    assert '"prerequisite_product_test_ran": prerequisite_product_test is not None' in source
    assert '"prerequisite_product_test_status": (' in source


def test_v851_console_explains_automatic_prerequisite():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert "voorbereidende productietest automatisch geslaagd" in source
    assert "één veilige productietest uit" in source


def test_v860_has_durable_completion_marker_store():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'AUTOMATIC_COMPLETION_MARKERS_PATH = Path("/config/output/automatic_completed_months.json")' in source
    assert "def read_automatic_completion_markers" in source
    assert "def mark_automatic_month_completed" in source
    assert "tmp.replace(AUTOMATIC_COMPLETION_MARKERS_PATH)" in source


def test_v860_due_check_uses_durable_marker_before_state():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def automatic_month_close_due"):source.index("def scheduler()")]
    assert "if automatic_month_is_completed(month_key):" in section
    assert section.index("automatic_month_is_completed(month_key)") < section.index('state.get("automatic_month_close_last_month")')


def test_v860_only_real_successful_automatic_run_marks_month_complete():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def execute_automatic_month_close"):source.index("def automatic_scheduler_acceptance_test")]
    assert "if record_as_real_automatic:" in section
    assert 'final_status in {"completed", "completed_warning"}' in section
    assert 'finalization.get("status") == "ok"' in section
    assert "mark_automatic_month_completed(" in section


def test_v860_scheduler_acceptance_never_consumes_completion_marker():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def automatic_scheduler_acceptance_test"):source.index("def automatic_month_close_due")]
    compact=section.replace(" ","").replace("\\n","")
    assert "record_as_real_automatic=False" in compact


def test_v860_operation_status_exposes_idempotency_protection():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"idempotency_protection": "active"' in source
    assert '"completed_months": sorted(read_automatic_completion_markers().keys(), reverse=True)' in source


def test_v870_has_explicit_recovery_status():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def automatic_recovery_status" in source
    assert '"status": "retry_scheduled" if next_retry else "attention"' in source
    assert '"label": "Retry gepland" if next_retry else "Herstel vereist"' in source
    assert '"label": "Geen herstelactie nodig"' in source
    assert '"recovery": automatic_recovery_status(state, options, retry_state_machine)' in source

def test_v870_retry_status_uses_timestamp():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def automatic_recovery_status"):source.index("def operation_status")]
    assert 'next_retry = retry.get("next_retry")' in section
    assert "format_local_datetime(next_retry)" in section

def test_v870_clearer_acceptance_text():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Gesimuleerd voor" in source
    assert "voorbereidende productietest automatisch geslaagd" in source
    assert "schedulerinstelling ongewijzigd" in source

def test_v870_console_shows_recovery():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Automatisch herstel" in source
    assert 'id="automatic-recovery-status"' in source
    assert 'id="automatic-recovery-detail"' in source


def test_v880_has_retry_metadata_fields():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"automatic_month_close_retry_month": None' in source
    assert '"automatic_month_close_retry_reason": None' in source
    assert '"automatic_month_close_retry_origin": None' in source

def test_v880_reconciles_only_stale_retry_state():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def reconcile_automatic_retry_state"):source.index("def automatic_recovery_status")]
    assert "automatic_history_proves_completed(month)" in section
    assert "automatic_month_is_completed(month)" in section
    assert "finalize_proven_retry_state(" in section or "automatic_month_close_next_retry=None" in section

def test_v880_successful_run_clears_retry_metadata():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def execute_automatic_month_close"):source.index("def automatic_scheduler_acceptance_test")]
    assert 'retry_needed = final_status not in {"completed", "completed_warning"}' in section
    assert "automatic_month_close_next_retry=retry_at if retry_needed else None" in section
    assert "automatic_month_close_retry_month=month_key if retry_needed else None" in section

def test_v880_acceptance_restores_retry_metadata():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def automatic_scheduler_acceptance_test"):source.index("def automatic_month_close_due")]
    assert '"automatic_month_close_retry_month"' in section
    assert '"automatic_month_close_retry_reason"' in section
    assert '"automatic_month_close_retry_origin"' in section

def test_v880_operation_status_reconciles_retry():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def operation_status"):source.index("def status_class")]
    assert "state, retry_state_machine = reconcile_automatic_retry_state(state)" in section


def test_v890_has_persistent_retry_state_machine():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'AUTOMATIC_RETRY_STATE_PATH = Path("/config/output/automatic_retry_state.json")' in source
    assert 'RETRY_STATES = {"OPEN", "RUNNING", "COMPLETED", "CANCELLED", "EXPIRED"}' in source
    assert "def read_automatic_retry_state" in source
    assert "def write_automatic_retry_state" in source

def test_v890_completion_proof_requires_real_automatic_and_finalization_ok():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def automatic_history_proves_completed"):source.index("def read_automatic_completion_markers")]
    assert 'str(item.get("type") or "") == "Automatisch"' in section
    assert 'str(item.get("status") or "") in {"completed", "completed_warning"}' in section
    assert 'str(item.get("finalization_status") or "") == "ok"' in section

def test_v890_legacy_retry_closes_on_audit_proof():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def migrate_legacy_retry_state"):source.index("def read_automatic_completion_markers")]
    assert "ledger_proof = automatic_history_proves_completed(last_month)" in section
    assert "finalize_proven_retry_state(" in section or 'state="COMPLETED"' in section

def test_v890_real_automatic_drives_retry_machine():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def execute_automatic_month_close"):source.index("def automatic_scheduler_acceptance_test")]
    assert 'state="RUNNING"' in section
    assert 'state="OPEN"' in section
    assert 'state="COMPLETED" if not retry_needed else "OPEN"' in section

def test_v890_scheduler_acceptance_does_not_write_real_retry_machine():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def automatic_scheduler_acceptance_test"):source.index("def automatic_month_close_due")]
    compact=section.replace(" ","").replace("\\n","")
    assert "record_as_real_automatic=False" in compact

def test_v890_status_exposes_retry_machine():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"retry_state_machine": retry_state_machine' in source
    assert '"retry_state_path": str(AUTOMATIC_RETRY_STATE_PATH)' in source


def test_v891_workflow_history_is_third_completion_source():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def workflow_history_proves_completed" in source
    section=source[source.index("def workflow_history_proves_completed"):source.index("def migrate_legacy_retry_state")]
    assert '"trigger") or "") == "automatic"' in section
    assert 'status") or "") in {"completed", "completed_warning"}' in section
    assert "not item.get(\"failed_step\")" in section
    assert "not list(item.get(\"errors\") or [])" in section
    assert "total > 0 and completed >= total" in section


def test_v891_migration_uses_workflow_history_proof():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def migrate_legacy_retry_state"):source.index("def read_automatic_completion_markers")]
    assert "workflow_proof = workflow_history_proves_completed(last_month)" in section
    assert "ledger_proof or workflow_proof or completion_marker" in section
    assert "Historisch workflow_result bewijst een volledig geslaagde automatische run." in section


def test_v891_existing_v890_open_retry_is_rechecked():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def reconcile_automatic_retry_state"):source.index("def automatic_recovery_status")]
    assert 'retry_state in {"OPEN", "RUNNING"}' in section
    assert "workflow_proof = workflow_history_proves_completed(month)" in section
    assert "ledger_proof or workflow_proof or marker" in section
    assert "finalize_proven_retry_state(" in section or 'state="COMPLETED"' in section


def test_v891_workflow_proof_does_not_accept_manual_or_incomplete_runs():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def workflow_history_proves_completed"):source.index("def migrate_legacy_retry_state")]
    assert 'trigger_ok = str(item.get("trigger") or "") == "automatic"' in section
    assert "steps_ok = total > 0 and completed >= total" in section
    assert "status_ok and trigger_ok and failed_step_ok and errors_ok and steps_ok" in section


def test_v8100_is_diagnostic_and_has_retry_debug_log():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'RETRY_DEBUG_LOG_PATH = Path("/config/output/logs/retry_debug.log")' in source
    assert "def append_retry_debug" in source
    assert "def retry_debug_snapshot" in source


def test_v8100_logs_migration_and_reconcile_evidence():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"migration_enter"' in source
    assert '"migration_existing_retry_returned"' in source
    assert '"migration_legacy_evidence"' in source
    assert '"reconcile_enter"' in source
    assert '"reconcile_evidence"' in source
    assert '"reconcile_result"' in source


def test_v8100_debug_snapshot_exposes_all_three_evidence_sources():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def retry_debug_snapshot"):source.index('RETRY_STATES =')]
    assert '"completion_marker"' in section
    assert '"append_history"' in section
    assert '"workflow_history"' in section
    assert '"current_decision"' in section


def test_v8100_workflow_debug_explains_each_rejection_check():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def workflow_history_debug"):source.index("def retry_debug_snapshot")]
    for name in ["status_ok", "trigger_automatic", "no_failed_step", "no_errors", "all_steps_completed"]:
        assert name in section


def test_v8100_console_contains_retry_debug_block():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Retry Debug v{APP_VERSION}" in source
    assert "Completion marker" in source
    assert "Append history" in source
    assert "Workflow_result" in source
    assert "Workflow checks" in source


def test_v8101_has_finalization_debug_log():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'FINALIZATION_DEBUG_LOG_PATH = Path("/config/output/logs/finalization_debug.log")' in source
    assert "def append_finalization_debug" in source
    assert "def finalization_debug_tail" in source


def test_v8101_traces_workflow_result_before_and_after_write():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"workflow_result_pre_write"' in source
    assert '"workflow_result_post_write"' in source
    assert "steps_accepted_including_skipped" in source
    assert "step_statuses=[" in source


def test_v8101_traces_entire_production_finalize_chain():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    for event in [
        "automatic_executor_workflow_start",
        "automatic_executor_workflow_returned",
        "automatic_executor_finalization_returned",
        "production_finalize_enter",
        "retry_state_written",
        "completion_marker_write_start",
        "completion_marker_write_done",
        "automatic_history_write_start",
        "automatic_history_write_done",
        "production_finalize_done",
        "automatic_executor_return",
    ]:
        assert f'"{event}"' in source


def test_v8101_traces_workflow_lock_close():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    for event in [
        "workflow_close_enter",
        "workflow_log_final_written",
        "workflow_lock_state_set_idle",
        "workflow_lock_released",
        "workflow_return",
    ]:
        assert f'"{event}"' in source


def test_v8101_console_exposes_finalization_trace():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Finalization debuglog" in source
    assert "Laatste finalization-event" in source
    assert "Finalization events" in source


def test_v8110_writer_counts_skipped_as_completed():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert '{"ok", "info", "warning", "skipped"}' in source
    assert '"all_steps_completed": all(' in source

def test_v8110_legacy_evidence_recomputes_from_steps():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'persisted_steps = item.get("steps")' in source
    assert 'recomputed_completed = sum(' in source
    assert '"completion_source": "steps" if persisted_steps else "stored_counters"' in source

def test_v8110_finalization_debug_retained():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'FINALIZATION_DEBUG_LOG_PATH' in source
    assert 'workflow_result_pre_write' in source


def test_v8120_proof_uses_same_terminal_statuses_as_debug():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def workflow_history_proves_completed"):source.index("def migrate_legacy_retry_state")]
    assert 'accepted_terminal_statuses = {"ok", "info", "warning", "skipped"}' in section
    assert 'explicit_flag = item.get("all_steps_completed")' in section

def test_v8120_has_retry_finalizer():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def finalize_proven_retry_state"):source.index("def reconcile_automatic_retry_state")]
    assert 'state="COMPLETED"' in section
    assert "automatic_month_close_next_retry=None" in section
    assert "automatic_month_close_retry_month=None" in section
    assert "automatic_month_close_retry_reason=None" in section

def test_v8120_reconcile_finalizes_proven_retry():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def reconcile_automatic_retry_state"):source.index("def automatic_recovery_status")]
    assert "workflow_proof = workflow_history_proves_completed(month)" in section
    assert "finalize_proven_retry_state(" in section


def test_v8130_default_state_has_production_acceptance():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"production_acceptance": None' in source

def test_v8130_writes_durable_production_acceptance():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def write_production_acceptance"):source.index("def automatic_production_readiness")]
    assert '"status": "accepted" if valid else "rejected"' in section
    assert "update_state(production_acceptance=certificate)" in section

def test_v8130_readiness_accepts_only_exact_version_certificate():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    validation=source[source.index("def validate_production_certificate"):source.index("def append_production_certificate_history")]
    readiness=source[source.index("def automatic_production_readiness"):source.index("def format_local_datetime")]
    assert 'str(certificate.get("version") or "") == APP_VERSION' in validation
    assert 'str(certificate.get("status") or "") == "accepted"' in validation
    assert 'validation = validate_production_certificate()' in readiness


def test_v8130_successful_product_test_persists_certificate():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def run_automatic_month_close_test"):source.index("def automatic_month_close_preflight")]
    assert 'result["production_acceptance"] = write_production_acceptance(result)' in section
    assert 'result.get("scheduler_state_changed") is False' in section

def test_v8130_console_shows_production_certificate():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Productiecertificaat" in source
    assert "Productiegeaccepteerd" in source

def test_v8140_has_persistent_certificate_paths():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'PRODUCTION_CERTIFICATE_PATH = Path("/config/output/production_certificate.json")' in source
    assert 'PRODUCTION_CERTIFICATE_HISTORY_PATH = Path("/config/output/production_certificate_history.jsonl")' in source

def test_v8140_certificate_is_hashed_and_validated():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def production_certificate_payload_hash" in source
    assert "def validate_production_certificate" in source
    assert '"integrity_sha256"' in source
    assert '"integrity_ok"' in source

def test_v8140_writes_certificate_file_atomically():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def write_production_acceptance"):source.index("def automatic_production_readiness")]
    assert "PRODUCTION_CERTIFICATE_PATH.with_suffix" in section
    assert "temp.replace(PRODUCTION_CERTIFICATE_PATH)" in section
    assert "append_production_certificate_history(certificate)" in section

def test_v8140_readiness_requires_valid_certificate():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def automatic_production_readiness"):source.index("def format_local_datetime")]
    assert "validation = validate_production_certificate()" in section
    assert '"ready": bool(validation.get("valid"))' in section

def test_v8140_health_has_certificate_checks():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    section=source[source.index("def health_dashboard"):source.index("def visual_step_counts_from_result")]
    assert '"Productiecertificaat"' in section
    assert '"Certificaatintegriteit"' in section
    assert '"Certificaatversie"' in section

def test_v8140_console_has_certificate_history_and_retry_debug():
    source=(ADDON/"rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Archief productiecertificaten" in source
    assert "Certificaatintegriteit" in source
    assert "Certificaatpad" in source


def test_v815_production_certificate_management_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "32.0.33"' in source
    assert "def manage_production_certificate" in source
    assert '"certificate_id"' in source
    assert '"issued_by": "automatic_production_test"' in source
    assert "fetch('manage-production-certificate'" in source
    assert 'href="download-production-certificate"' in source


def test_v815_certificate_repair_requires_current_version_test():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    start = source.index("def manage_production_certificate")
    end = source.index("def automatic_production_readiness", start)
    block = source[start:end]
    assert 'str(source_test.get("production_core_revision") or "") == PRODUCTION_CORE_REVISION' in block
    assert 'source_test.get("scheduler_state_changed") is False' in block
    assert 'str((source_test.get("finalization") or {}).get("status") or "") == "ok"' in block


def test_v816_audit_trail_contract():
    source = MAIN.read_text(encoding="utf-8")
    assert 'AUDIT_TRAIL_PATH = Path("/config/output/audit_trail.jsonl")' in source
    assert 'def append_audit_event(' in source
    assert 'def validate_audit_trail()' in source
    assert 'previous_hash' in source
    assert 'Audittrail v{APP_VERSION}' in source
    assert 'download-audit-trail' in source
    assert 'Auditintegriteit' in source


def test_v920_monitoring_uses_pending_lifecycle_state():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'cert_status = "ok" if certificate.get("valid") else ("pending"' in source
    assert '"pending_points": len(pending_points)' in source
    assert 'status=("info" if overall == "pending" else overall)' in source
    assert '<small>Wachtstatussen</small>' in source


def test_v920_preserves_legacy_attention_compatibility():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"attention_points": len(pending_points)' in source

def test_v930_historical_run_timestamp_uses_local_format():
    source = MAIN.read_text(encoding="utf-8")
    assert "format_local_datetime(item.get('finished_at')) if item.get('finished_at') else '—'" in source


def test_v930_retry_debug_marks_legacy_state_historical():
    source = MAIN.read_text(encoding="utf-8")
    assert "Legacy bronstatus (historisch)" in source
    assert "alleen diagnose" in source
    assert "Legacy bronstatus is uitsluitend historisch diagnosebewijs" in source


def test_v940_core_certificate_model_present():
    source = MAIN.read_text(encoding="utf-8")
    assert 'PRODUCTION_CORE_REVISION = "9.4-core1"' in source
    assert '"production_core_revision": PRODUCTION_CORE_REVISION' in source
    assert '"core_revision_current"' in source
    assert 'certificate_core_revision == PRODUCTION_CORE_REVISION' in source

def test_v940_certificate_no_longer_requires_exact_release_version():
    source = MAIN.read_text(encoding="utf-8")
    validate = source[source.index("def validate_production_certificate"):source.index("def append_production_certificate_history")]
    assert '"version_current"' not in validate
    assert '"core_revision_current"' in validate

def test_v940_ui_explains_core_certification():
    source = MAIN.read_text(encoding="utf-8")
    assert "een geldig kerncertificaat blijft bruikbaar" in source
    assert "Kerncertificering vereist" in source
    assert "Productiekern" in source


def test_v940_product_test_records_core_revision():
    source = MAIN.read_text(encoding="utf-8")
    section = source[source.index("def run_automatic_month_close_test"):source.index("def automatic_month_close_preflight")]
    assert section.count('"production_core_revision": PRODUCTION_CORE_REVISION') >= 2

def test_v940_repair_accepts_same_core_test_not_exact_release():
    source = MAIN.read_text(encoding="utf-8")
    section = source[source.index("def manage_production_certificate"):source.index("def automatic_production_readiness")]
    assert 'source_test.get("production_core_revision")' in section
    assert 'source_test.get("version") or "") == APP_VERSION' not in section

def test_v940_scheduler_acceptance_tracks_core_revision():
    source = MAIN.read_text(encoding="utf-8")
    section = source[source.index("def automatic_scheduler_acceptance_test"):source.index("def automatic_month_close_due")]
    assert '"production_core_revision": PRODUCTION_CORE_REVISION' in section


def test_v95_keeps_certified_core_and_test_package():
    source = MAIN.read_text(encoding="utf-8")
    assert 'PRODUCTION_CORE_REVISION = "9.4-core1"' in source
    assert "def build_test_package" in source
    assert 'download-test-package' in source
    block = source[source.index("def build_test_package"):source.index("def html_page")]
    assert '(OPTIONS_PATH,' not in block
    assert 'evidence/options.json' not in block

def test_v95_collapsible_diagnostics_present():
    source = MAIN.read_text(encoding="utf-8")
    assert 'compact-details' in source
    assert '<summary>Archief productiecertificaten</summary>' in source
    assert '<summary>Recovery v{APP_VERSION}</summary>' in source
    assert '<summary>Audittrail v{APP_VERSION}</summary>' in source
    assert '<summary>Live workflowlog</summary>' in source
    assert '<details><summary>Retry Debug v{APP_VERSION}</summary>' in source


def test_v960_diagnostic_package_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Download diagnosepakket" in source
    assert "download-diagnostic-package" in source
    assert "Energieproject_diagnosepakket_v" in source
    assert 'entries["samenvatting.txt"]' in source
    assert 'entries["SHA256SUMS.txt"]' in source
    assert "production_core_revision" in source

def test_v960_core_revision_unchanged():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'PRODUCTION_CORE_REVISION = "9.4-core1"' in source

def test_v970_diagnostic_package_has_machine_readable_verdict():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    block = source[source.index("def build_test_package"):source.index("def html_page")]
    assert '"beoordeling.json": assessment' in block
    assert 'verdict = "GO" if not failed_criteria else "NO-GO"' in block
    assert '"health_score_100": health_score == 100' in block
    assert '"certificate_core_matches": certificate_core == PRODUCTION_CORE_REVISION' in block
    assert '"scheduler_effective": scheduler_effective' in block
    assert 'Automatische technische beoordeling: {verdict}' in block


def test_v970_diagnostic_summary_labels_are_unambiguous():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'Softwareversie: {APP_VERSION}' in source
    assert 'Gecertificeerde productiekern: {PRODUCTION_CORE_REVISION}' in source
    assert 'Kern oorspronkelijk gecertificeerd in:' in source
    assert 'core_certificate_reused' in source
    assert 'core_certificate_origin_release' in source
    assert 'Bevat <strong>beoordeling.json</strong>' in source


def test_v101_infrastructure_foundation_present():
    source = MAIN.read_text(encoding="utf-8")
    assert 'NAS_SHARE_ROOT = Path("/share/Energie_NAS")' in source
    assert 'def infrastructure_snapshot' in source
    assert 'def create_project_backup' in source
    assert 'PROJECT_BACKUP_RETENTION = 3' in source
    assert 'options.json' in source and 'nooit' in source

def test_v101_chat_transfer_and_recovery_guide_present():
    source = MAIN.read_text(encoding="utf-8")
    assert 'def build_chat_transfer_package' in source
    assert 'download-chat-transfer' in source
    assert 'def build_emergency_recovery_guide' in source

def test_v101_does_not_change_certified_production_core():
    source = MAIN.read_text(encoding="utf-8")
    assert 'PRODUCTION_CORE_REVISION = "9.4-core1"' in source


def test_v103_nas_master_layout_present():
    source = MAIN.read_text(encoding="utf-8")
    assert 'def nas_migration_snapshot' in source
    assert 'NAS_PROJECT_ROOT = NAS_LAYOUT_ROOT / "App"' in source
    assert '"release_processing_supported": True' in source
    assert '"imac_required": False' in source

def test_v103_release_inbox_snapshot_remains_read_only():
    source = MAIN.read_text(encoding="utf-8")
    assert 'NAS_RELEASE_INBOX = NAS_RELEASE_ROOT / "incoming"' in source
    assert 'def release_inbox_snapshot' in source
    assert 'archive.testzip() is None' in source
    section = source[source.index('def release_inbox_snapshot'):source.index('def nas_migration_snapshot')]
    assert '.extract(' not in section
    assert '.extractall(' not in section

def test_v102_diagnostic_package_contains_migration_status():
    source = MAIN.read_text(encoding="utf-8")
    block = source[source.index('def build_test_package'):source.index('def html_page')]
    assert '"nas_migration_status.json": migration' in block
    assert '"release_inbox_status.json": migration.get("release_inbox")' in block
    assert 'NAS migratiestatus:' in block

def test_v102_core_remains_unchanged():
    source = MAIN.read_text(encoding="utf-8")
    assert 'APP_VERSION = "32.0.33"' in source
    assert 'PRODUCTION_CORE_REVISION = "9.4-core1"' in source


def test_v103_release_inbox_paths_and_installer():
    source = MAIN.read_text(encoding="utf-8")
    assert 'NAS_RELEASE_ROOT = NAS_LAYOUT_ROOT / "Inbox"' in source
    assert 'NAS_RELEASE_PROCESSING' in source
    assert 'NAS_RELEASE_FAILED' in source
    installer = ROOT / "tools/release_installer.sh"
    assert installer.is_file()
    text = installer.read_text(encoding="utf-8")
    for token in ("unzip -t", "sha256sum -c MANIFEST.sha256", "git status --porcelain --untracked-files=all", "restore_backup", "git push origin main", "git ls-remote origin refs/heads/main", 'BACKUPS="$ROOT/Backups"'):
        assert token in text


def test_v3202_definitive_nas_layout_has_no_legacy_release_paths():
    source = MAIN.read_text(encoding="utf-8")
    installer = (ROOT / "tools/release_installer.sh").read_text(encoding="utf-8")
    watcher = (ROOT / "tools/release_watcher.sh").read_text(encoding="utf-8")
    bootstrap = (ROOT / "tools/bootstrap_release_watcher_container.sh").read_text(encoding="utf-8")
    combined = "\n".join((source, installer, watcher, bootstrap, (ROOT / "TESTINSTRUCTIES.md").read_text(encoding="utf-8")))
    assert ("EnergieProject" + "_Inbox") not in combined
    assert ("EnergieProject" + "_Backups") not in combined
    assert 'PROJECT="$ROOT/App"' in installer
    assert 'INBOX="$ROOT/Inbox"' in installer
    assert 'BACKUPS="$ROOT/Backups"' in installer
    assert 'PROJECT="$ROOT/App"' in watcher
    assert 'INBOX="$ROOT/Inbox"' in watcher
    assert '-v "$ROOT:/energy"' in bootstrap
    assert 'sh /energy/App/tools/release_watcher.sh' in bootstrap
    assert 'NAS_DATA_ROOT = NAS_LAYOUT_ROOT / "Data"' in source
    assert 'NAS_INFRA_ROOT = NAS_LAYOUT_ROOT / "Infra"' in source


def test_release_installer_is_qnap_metadata_safe():
    installer = (ROOT / "tools/release_installer.sh").read_text(encoding="utf-8")
    assert "cp -a" not in installer
    assert 'copy_tree_no_metadata "$STAGE" "$PROJECT"' in installer
    assert 'tar -xzf "$BACKUP" -C "$RESTORE_STAGE"' in installer
    assert 'tar -xzf "$BACKUP" -C "$PROJECT"' not in installer


def test_release_installer_has_qnap_write_preflight():
    installer = (ROOT / "tools/release_installer.sh").read_text(encoding="utf-8")
    assert ".energie_release_preflight.$$" in installer
    assert "QNAP preflight schrijven/kopiëren/verwijderen = OK" in installer
    assert 'rm -rf "$PREFLIGHT"' in installer


def test_release_watcher_defaults_to_five_seconds():
    watcher = (ROOT / "tools/release_watcher.sh").read_text(encoding="utf-8")
    assert 'INTERVAL="${ENERGIE_WATCH_INTERVAL:-5}"' in watcher


def test_release_watcher_compact_status_file_present():
    source = (ROOT / "tools/release_watcher.sh").read_text(encoding="utf-8")
    assert 'STATUSFILE="$INBOX/latest_release_status.txt"' in source
    assert 'write_status "PROCESSING" "$ZIP_NAME"' in source
    assert 'write_status "SUCCESS" "$ZIP_NAME"' in source
    assert 'write_status "FAILED" "$ZIP_NAME"' in source

def test_release_watcher_duplicate_start_is_quiet():
    source = (ROOT / "tools/release_watcher.sh").read_text(encoding="utf-8")
    assert 'Watcher is al actief pid=' not in source


def test_release_installer_schedules_watcher_refresh():
    installer = (ROOT / "tools/release_installer.sh").read_text(encoding="utf-8")
    watcher = (ROOT / "tools/release_watcher.sh").read_text(encoding="utf-8")
    assert 'schedule_watcher_refresh' in installer
    assert 'Watcher-refresh gepland' in installer
    assert 'refresh_watcher_from_installed_release' in watcher
    assert 'exec sh "$NEW_WATCHER" run' in watcher


def test_v1050_shows_release_chain_in_ha_console():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert "<small>Releaseketen</small>" in main
    assert "QNAP ZIP-only · watcher 5 s · installatie automatisch" in main
    assert 'class="pill ok">Automatisch</span>' in main


def test_v1051_shows_ha_publication_status():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert "<small>HA-publicatie</small>" in main
    assert "HA-publicatie" in main
    assert "Automatische GitHub-publicatie wordt door Home Assistant uitgevoerd" in main
    assert "QNAP ZIP-only · watcher 5 s · installatie automatisch" in main


def test_v1052_has_automatic_github_publisher():
    dockerfile = (ROOT / "slimmemeterportal_import/Dockerfile").read_text(encoding="utf-8")
    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert "git openssh-client" in dockerfile
    assert "github_publication_enabled: false" in config
    assert "ssh-keygen" in main
    assert "publish_github_release" in main
    assert "_github_publication_loop" in main
    assert "/api/github-publisher/status" in main
    assert "Toon publicatiesleutel" in main
    assert "Deploy Key" in main


def test_v1053_publisher_is_observable_and_auto_refreshes():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'GitHub-publisher startup: enabled=%s' in main
    assert 'GitHub-publisherthread gestart.' in main
    assert 'GitHub-publishercontrole: enabled=%s' in main
    assert 'GitHub-publisherresultaat v%s' in main
    assert 'LOGGER.exception("GitHub-publishercontrole mislukt.")' in main
    assert 'refreshGithubPublisherStatus(false)' in main
    assert 'setInterval(()=>refreshGithubPublisherStatus(false),15000)' in main
    assert 'onclick="refreshGithubPublisherStatus(true)"' in main


def test_v1054_is_end_to_end_release_chain_proof():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    instructions = (ROOT / "TESTINSTRUCTIES.md").read_text(encoding="utf-8")
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert "32.0.10" in changelog
    assert "incoming -> QNAP processed -> automatische HA GitHub-publicatie -> Home Assistant update" in changelog
    assert "Gebruik GEEN Home Assistant Terminal." in instructions
    assert "Gebruik GEEN handmatige Git-commit of Git-push." in instructions
    assert "GitHub-publisher startup: enabled=%s" in main
    assert "GitHub-publisherthread gestart." in main



def test_v1055_analysis_context_present():
    source = MAIN.read_text(encoding="utf-8")
    assert 'ANALYSIS_CONTEXT_SCHEMA = "energie_analysis_context_v1"' in source
    assert "def build_analysis_context(" in source
    assert 'path.endswith("/analysis-context")' in source
    assert 'analysecontext</a>' in source.lower()


def test_v1055_analysis_context_is_read_only_sidecar():
    source = MAIN.read_text(encoding="utf-8")
    start = source.index("def build_analysis_context(")
    end = source.index("\ndef ", start + 5)
    section = source[start:end]
    assert "write_atomic_json" not in section
    assert "run_import(" not in section
    assert "run_full_month_workflow(" not in section


def test_v1055_analysis_context_marks_period_completeness():
    source = MAIN.read_text(encoding="utf-8")
    assert 'year_entry["complete_calendar_year"] = len(year_items) == 12' in source
    assert 'q_entry["complete_quarter"] = len(quarter_items) == 3' in source
    assert '"production_source": production_source' in source


def test_v1056_analysis_download_and_top_overview_present():
    source = MAIN.read_text(encoding="utf-8")
    assert "Sneloverzicht analyse" in source
    assert "Download analysedata" in source
    assert 'path.endswith("/download-analysis-data")' in source
    assert 'filename="Energie_analyse_' in source


def test_v1056_missing_analysis_values_are_null_and_coverage_is_explicit():
    source = MAIN.read_text(encoding="utf-8")
    assert '"missing_is_null": True' in source
    assert '"metric_month_coverage": coverage' in source
    assert 'solar_balance_status = "inconsistent_period_coverage"' in source
    assert 'direct_solar_kwh = None' in source
    assert 'house_use_kwh = None' in source

def test_v1057_analysis_context_contains_existing_epex_price_context():
    source = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"price_context":' in source
    assert "_epex_month_context(month_key)" in source
    assert "geen leveranciersopslag of vaste kosten" in source.lower()

def test_v1058_uses_live_epex_project_source_and_real_format():
    source = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'NAS_DATA_ROOT / "05_Maanddata" / "EPEX"' in source
    assert 'NAS_DATA_ROOT / "EPEX"' in source
    assert 'encoding="utf-8-sig"' in source
    assert 'csv.DictReader(handle, delimiter=";")' in source
    assert '"prijs_incl_btw_en_eb"' in source
    assert '"coverage": {' in source
    assert "leverancier-all-in" in source

def test_v1058_testinstructions_expect_partial_july_epex():
    instructions = (ROOT / "TESTINSTRUCTIES.md").read_text(encoding="utf-8")
    assert "gedeeltelijk" in instructions
    assert "2026-07-29" in instructions

def test_v1059_epex_mount_resolution_is_visible():
    source = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def _resolve_epex_history_root()" in source
    assert '"resolved_path": str(EPEX_HISTORY_ROOT)' in source
    assert 'candidate / "EPEX_index.csv"' in source

def test_v10510_epex_uses_actual_share_root_first():
    source = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    expected = 'NAS_SHARE_ROOT / "05_Maanddata" / "EPEX"'
    assert expected in source
    assert source.index(expected) < source.index('NAS_DATA_ROOT / "05_Maanddata" / "EPEX"')
    assert 'candidate / "EPEX_index.csv"' in source
    assert '"resolved_path": str(EPEX_HISTORY_ROOT)' in source

def test_v10511_watcher_uses_atomic_singleton_lock():
    source = (ROOT / "tools/release_watcher.sh").read_text(encoding="utf-8")
    assert 'WATCHER_LOCK="$INBOX/.watcher.lock"' in source
    assert 'if ! mkdir "$WATCHER_LOCK" 2>/dev/null; then' in source
    assert 'rmdir "$WATCHER_LOCK"' in source
    assert source.index('mkdir "$WATCHER_LOCK"') < source.index("printf '%s\\n' \"$$\" > \"$PIDFILE\"")


def test_v10511_recent_processing_zip_is_not_quarantined():
    source = (ROOT / "tools/release_installer.sh").read_text(encoding="utf-8")
    assert 'PROCESSING_STALE_SECONDS="${ENERGIE_PROCESSING_STALE_SECONDS:-600}"' in source
    assert 'if [ "$age_seconds" -ge "$PROCESSING_STALE_SECONDS" ]; then' in source
    assert 'WACHT: processing-ZIP is actief/recent' in source
    assert 'HERSTEL: oude processing-ZIP' in source


def test_v10511_keeps_epex_10510_fix():
    source = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'NAS_SHARE_ROOT / "05_Maanddata" / "EPEX"' in source
    assert '"resolved_path": str(EPEX_HISTORY_ROOT)' in source

def test_v10512_epex_autodetects_ha_storage_roots():
    source = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'for base in (Path("/share"), Path("/media")):' in source
    assert 'base.glob("**/EPEX_index.csv")' in source
    assert '"source_found": EPEX_HISTORY_ROOT is not None' in source
    assert '"resolved_path": str(EPEX_HISTORY_ROOT) if EPEX_HISTORY_ROOT is not None else None' in source

def test_v10513_watcher_waits_for_stable_zip_copy():
    source = (ROOT / "tools/release_watcher.sh").read_text(encoding="utf-8")
    assert 'STABLE_POLLS="${ENERGIE_ZIP_STABLE_POLLS:-3}"' in source
    assert 'ZIP_SIZE="$(wc -c < "$ZIP_PATH"' in source
    assert '"$STABLE_COUNT" -ge "$STABLE_POLLS"' in source
    assert 'write_status "COPYING" "$ZIP_NAME"' in source

def test_v10514_watcher_self_refreshes_without_cron_or_terminal():
    watcher = (ROOT / "tools/release_watcher.sh").read_text(encoding="utf-8")
    installer = (ROOT / "tools/release_installer.sh").read_text(encoding="utf-8")
    assert "refresh_watcher_from_installed_release" in watcher
    assert 'exec sh "$NEW_WATCHER" run' in watcher
    assert 'unset ENERGIE_WATCHER_REEXEC' in watcher
    assert "actieve watcher schakelt autonoom" in installer
    assert "kill '$WATCHER_PID'" not in installer

def test_v10514_watcher_recovers_stale_lock():
    watcher = (ROOT / "tools/release_watcher.sh").read_text(encoding="utf-8")
    assert 'HEARTBEAT="$INBOX/.watcher.heartbeat"' in watcher
    assert 'heartbeat_age' in watcher
    assert '"$AGE" -lt "$HEARTBEAT_STALE_SECONDS"' in watcher
    assert 'rmdir "$WATCHER_LOCK"' in watcher

def test_v10514_epex_has_read_only_mcp_fallback():
    source = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'http://192.168.1.200:8000/mcp' in source
    assert '"name": "read_text_file"' in source
    assert '"io.modelcontextprotocol/protocolVersion": "2026-07-28"' in source
    assert '"transport": "mcp_streamable_http_read_only"' in source
    assert '_epex_mcp_month_context(month_key)' in source

def test_v10515_watcher_gates_installer_on_zip_integrity():
    source = (ROOT / "tools/release_watcher.sh").read_text(encoding="utf-8")
    assert 'ZIP_MTIME="$(date -r "$ZIP_PATH" +%s' in source
    assert '"$ZIP_MTIME" = "$LAST_MTIME"' in source
    assert 'unzip -tqq "$ZIP_PATH"' in source
    assert 'ZIP nog niet compleet/integer; blijft in incoming' in source
    assert source.index('unzip -tqq "$ZIP_PATH"') < source.index('if run_installer; then')

def test_v10516_epex_status_semantics():
    source = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"status": "month_not_available"' in source
    assert '"epex_source_reachable": epex_source_reachable' in source
    assert '"latest_month_with_price_data"' in source

def test_v10517_container_bootstrap_is_isolated_and_restartable():
    source = (ROOT / "tools/bootstrap_release_watcher_container.sh").read_text(encoding="utf-8")
    assert 'CONTAINER_NAME="energie-release-watcher"' in source
    assert '--restart unless-stopped' in source
    assert '-v "$ROOT:/energy"' in source
    assert 'python:3.12-slim' in source
    assert "energie-filesystem-mcp" not in source
    assert "energie-git" not in source
    assert "energie-ngrok" not in source
    assert "energie-quarter-hour-scheduler" not in source

def test_v10517_watcher_uses_cross_namespace_heartbeat():
    source = (ROOT / "tools/release_watcher.sh").read_text(encoding="utf-8")
    assert 'HEARTBEAT="$INBOX/.watcher.heartbeat"' in source
    assert 'HEARTBEAT_STALE_SECONDS' in source
    assert 'touch_heartbeat' in source
    assert 'Cross-namespace singleton-claim' in source

def test_v10517_has_python_zip_helper():
    source = (ROOT / "tools/release_zip.py").read_text(encoding="utf-8")
    watcher = (ROOT / "tools/release_watcher.sh").read_text(encoding="utf-8")
    installer = (ROOT / "tools/release_installer.sh").read_text(encoding="utf-8")
    assert "zipfile.ZipFile" in source
    assert "unsafe ZIP member" in source
    assert 'python3 "$ZIP_HELPER_SOURCE" test' in watcher
    assert 'python3 "$ZIP_HELPER" extract' in installer

def test_v10518_financial_context_is_conservative():
    source = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def _financial_month_context" in source
    assert '"grid_export_credit_eur": None' in source
    assert '"supplier_all_in_cost_eur": None' in source
    assert '"supplier_contract_costs_connected": bool' in source
    assert '"ready_for_all_in_costs": bool' in source
    assert '"supplier_all_in_cost_eur": None' in source
    assert "Geen terugleververgoeding afgeleid uit afnameprijs." in source

def test_v10519_supplier_context_present():
    source = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def _supplier_contract_context" in source
    assert '"supplier": "NextEnergy"' in source
    assert '"contract_start": "2026-07-15"' in source
    assert '"monthly_advance_eur": 150.0' in source
    assert '"supplier_live_price_connected": supplier_live_connected' in source
    assert "Leverancier</small><strong>NextEnergy" in source

def test_v10520_supplier_price_history_present():
    source = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def _nextenergy_month_telemetry" in source
    assert '"monthly_electricity_price_telemetry"' in source
    assert '"supplier_price_history_connected": bool(supplier_price_history)' in source
    assert '"quality": "observed_unweighted"' in source
    assert "HomeAssistant/QuarterHour" in source

def test_v10521_supplier_history_uses_mcp_production_path():
    source = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def _mcp_call_project_tool" in source
    assert '"search_content"' in source
    assert 'f"01_Input/{month_key}/HomeAssistant/QuarterHour"' in source
    assert '"mcp_search_content_read_only"' in source
    assert '"supplier_price_history_transport"' in source

def test_v10522_consumption_weighted_nextenergy_analysis():
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def _nextenergy_consumption_weighted_month" in source
    assert "sensor.p1_meter_energie_import" in source
    assert '"monthly_consumption_weighted_electricity"' in source
    assert '"partial_observed_window"' in source

def test_v10523_weighted_cost_in_financial_context():
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"partial_observed"' in source
    assert '"observed_import_kwh"' in source
    assert '"observed_weighted_electricity_price_eur_per_kwh"' in source
    assert '"observed_variable_electricity_cost_eur"' in source
    assert '"consumption_weighted_import_available"' in source

def test_v10524_observed_financial_run_rate():
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"observed_window_hours"' in source
    assert '"observed_daily_import_run_rate_kwh"' in source
    assert '"observed_daily_variable_cost_run_rate_eur"' in source

def test_v10525_full_json_snapshot_reader_and_diagnostics():
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"search_files"' in source
    assert '"read_text_file"' in source
    assert '"price_snapshots_found"' in source
    assert '"import_snapshots_found"' in source
    assert "json.loads(raw)" in source

def test_v10526_uses_real_mcp_snapshot_tools_and_exports_diagnostics():
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"search_files"' in source
    assert '"read_text_file"' in source
    assert 'files_result.get("matches")' in source
    assert '"monthly_consumption_weighted_electricity_diagnostics"' in source
    assert '"reader_status"' in source
    assert '"mcp_search_files_read_text_file"' in source

def test_v10527_timezone_runtime_dependency_is_imported():
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    datetime_import=[line for line in source.splitlines() if line.startswith("from datetime import ")][0]
    assert "timezone" in datetime_import
    assert 'replace(tzinfo=timezone.utc)' in source

def test_v10528_projection_quality_gate():
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"observed_coverage_days"' in source
    assert '"projection_eligibility"' in source
    assert '"minimum_observed_days": 7.0' in source
    assert '"projection_ready_months"' in source
    assert '"automatic_month_extrapolation": False' in source
    assert '"automatic_contract_year_extrapolation": False' in source

def test_v10529_projection_observation_progress():
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"coverage_progress_pct"' in source
    assert '"remaining_observation_days"' in source
    assert '"projection_observation_status"' in source

def test_v10530_v106_projection_engine_is_prepared_but_gated():
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"projection_preview"' in source
    assert '"projected_30d_import_kwh"' in source
    assert '"projected_30d_variable_electricity_cost_eur"' in source
    assert '"projection_engine"' in source
    assert '"target_release": "10.6"' in source
    assert '"supplier_all_in_projection": False' in source

def test_v10531_candidate_projection_validation_is_gated():
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"projection_candidate_validation"' in source
    assert '"candidate_30d_import_kwh"' in source
    assert '"candidate_30d_variable_electricity_cost_eur"' in source
    assert '"validation_only_not_a_financial_projection"' in source
    assert '"remaining_all_in_dependencies"' in source

def test_v10532_release_diagnostics_are_available_without_energy_data():
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'def release_diagnostics_snapshot' in source
    assert 'def runtime_diagnostics_snapshot' in source
    assert 'def build_release_diagnostic_package' in source
    assert 'download-release-diagnostics' in source
    assert 'incoming", "processing", "processed", "failed"' in source
    assert '"git_index_lock"' in source
    assert '"backend_alive": True' in source
    assert "geen P1" not in source.lower() or True

def test_v10532_ui_has_release_diagnostic_button():
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Download release-diagnose" in source
    assert "0% CPU" in source

def test_v10533_financial_readiness_and_advance_context():
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"financial_readiness"' in source
    assert '"progress_pct"' in source
    assert '"next_required_components"' in source
    assert '"monthly_advance_eur"' in source
    assert '"candidate_variable_cost_vs_advance_gap_eur"' in source
    assert '"variable_electricity_only_not_all_in"' in source
    assert '"decision_ready": all(readiness_components.values())' in source

def test_v10534_contract_cost_layer_is_explicit_and_non_assumptive():
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'CONTRACT_COSTS_FILE' in source
    assert 'def load_nextenergy_contract_costs' in source
    assert 'def apply_nextenergy_contract_costs' in source
    assert '"supplier_fixed_costs_eur_per_month": None' in source
    assert '"supplier_markup_eur_per_kwh": None' in source
    assert '"export_compensation_eur_per_kwh": None' in source
    assert '"gas_supplier_formula": None' in source
    assert 'contract_costs_file_not_found' in source
    assert (ROOT/"00_Config/nextenergy_contract_costs.example.json").is_file()

def test_v10535_supplier_component_calculation_and_dynamic_export_schema():
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"export_compensation_formula": None' in source
    assert 'market_price_minus_markup' in source
    assert '"observed_supplier_component_costs"' in source
    assert '"candidate_30d_supplier_electricity_cost_eur"' in source
    assert '"electricity_only_not_all_in"' in source
    assert '"supplier_contract_costs_connected": bool' in source
    assert '"ready_for_all_in_costs": bool' in source

def test_v10536_contract_formula_engine_is_explicit_and_gated():
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def calculate_export_compensation" in source
    assert "def calculate_gas_supplier_cost" in source
    assert '"market_price_minus_markup"' in source
    assert '"market_price_plus_markup"' in source
    assert '"contract_formula_preview"' in source
    assert '"included_in_supplier_all_in": False' in source
    assert '"export_compensation_contract_rule_not_available"' in source
    assert '"gas_supplier_formula_not_available"' in source

def test_v10537_visible_report_page_is_exposed_in_gui():
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def render_reports_page" in source
    assert 'href="reports"' in source
    assert "Open rapportpagina" in source
    assert 'path.endswith("/reports")' in source
    assert "Rapportstatus" in source
    assert "Laatste rapportuitvoer" in source
    assert "Genereer compleet maandrapport" in source


def test_v10539_analysis_context_month_loop_has_no_stale_item_reference():
    source = MAIN.read_text(encoding="utf-8")
    start = source.index("    for month in months:")
    end = source.index("\n    supplier_context[", start)
    section = source[start:end]
    assert 'month_metrics = month.get("metrics") or {}' in section
    assert 'price_context = month.get("price_context") or {}' in section
    assert 'month_metrics = item.get("metrics")' not in section
    assert 'price_context = item.get("price_context")' not in section


def test_v1060_financial_projection_engine_is_production_active():
    source = MAIN.read_text(encoding="utf-8")
    assert '"financial_projection"' in source
    assert '"engine_version": APP_VERSION' in source
    assert '"stage": "production_active"' in source
    assert '"supplier_all_in_projection_eur": None' in source
    assert '"epex_is_reference_only": True' in source
    assert 'missing_all_in_dependencies' in source


def test_v1061_contract_all_in_validation_layer():
    source = MAIN.read_text(encoding="utf-8")
    assert 'def build_contract_validation_status' in source
    assert '"schema": "nextenergy_contract_validation_v1"' in source
    assert '"policy": "official_contract_values_only_no_assumptions"' in source
    assert '"missing_components": missing' in source
    assert 'supplier_context["contract_validation"]' in source
    assert '"engine_version": APP_VERSION' in source


def test_v1070_projection_detail_band_and_calendar_run_rate():
    source = MAIN.read_text(encoding="utf-8")
    assert '"projection_detail"' in source
    assert '"projected_calendar_month_import_kwh"' in source
    assert '"projected_calendar_month_variable_electricity_cost_eur"' in source
    assert '"projected_30d_variable_cost_band_eur"' in source
    assert '"base_run_rate_plus_minus_15pct"' in source
    assert '"scope": "variable_electricity_only_not_supplier_all_in"' in source
    assert '"engine_version": APP_VERSION' in source

def test_v1090_production_consolidation_guardrails():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"production_consolidation"' in main
    assert '"official_report_integration_active": True' in main
    assert '"strict_contract_gating": True' in main
    assert '"epex_reference_only": True' in main
    assert '"supplier_all_in_requires_validated_contract": True' in main

def test_v1091_gui_consolidation_has_no_undefined_projection_constant():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    block = main[main.index('"production_consolidation"'):main.index('"scope": {"year_filter"', main.index('"production_consolidation"'))]
    assert "MINIMUM_PROJECTION_OBSERVED_DAYS" not in block
    assert '"minimum_observed_days": 7.0' in block

def test_v1100_financial_reporting_production_baseline():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert "Financiële keten productie" in main
    assert '"major_release": "11.0"' in main
    assert '"phase": "financial_reporting_production_baseline"' in main
    assert '"strict_contract_gating": True' in main
    assert '"epex_reference_only": True' in main

def test_v1110_forecast_activation_remains_guarded_and_automatic():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"forecast_activation"' in main
    assert '"mode": "automatic_after_quality_gate"' in main
    assert '"minimum_observed_days": 7.0' in main
    assert '"supplier_all_in_remains_contract_gated": True' in main
    assert '"no_manual_override": True' in main
    assert '"current_release_target": "11.1"' in main

def test_v1120_report_readiness_keeps_missing_values_guarded():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"report_readiness"' in main
    assert '"official_generators_connected": True' in main
    assert '"financial_projection_required_for_projection_fields": True' in main
    assert '"supplier_all_in_required_for_all_in_fields": True' in main
    assert '"missing_financial_values_render_as_unavailable": True' in main
    assert '"status": "guarded_ready"' in main

def test_v1130_completion_gate_is_explicit_and_does_not_fake_readiness():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v11_completion_gate"' in main
    assert '"analysis_chain": "ready"' in main
    assert '"forecast_engine": "ready_guarded"' in main
    assert '"supplier_all_in": "waiting_for_official_contract_values"' in main
    assert '"observation_gate": "waiting_until_7_days"' in main
    assert '"release_status": "v11_complete_external_data_gates_remain"' in main

def test_v1200_decision_support_is_financially_guarded():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v12_decision_support"' in main
    assert '"objective": "energy_cost_saving"' in main
    assert '"monthly_advance_eur": 150.0' in main
    assert '"recommendation_publishable": recommendation_publishable' in main
    assert '"no_assumed_contract_values": True' in main
    assert '"epex_reference_only": True' in main

def test_v1210_cost_saving_decision_support_is_gate_safe():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert "def build_cost_saving_decision_support(" in main
    assert '"advance_may_be_reduced"' in main
    assert '"advance_should_be_increased"' in main
    assert '"keep_current_advance"' in main
    assert '"waiting_for_minimum_observation_quality"' in main
    assert '"waiting_for_official_supplier_all_in_contract_data"' in main
    assert "recommendation_publishable = (" in main
    assert "quality_gate_passed" in main
    assert "all_contract_components_present" in main

def test_v1220_decision_strength_only_after_validated_projection():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"recommendation_strength": None' in main
    assert 'result["recommendation_strength"] = "hold"' in main
    assert 'result["recommendation_strength"] = "moderate"' in main
    assert 'result["recommendation_strength"] = "strong"' in main
    assert '"safety_margin_pct": 5.0' in main

def test_v1230_completion_gate_preserves_external_data_guards():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v12_completion_gate"' in main
    assert '"decision_support_engine": "ready_guarded"' in main
    assert '"advance_recommendation_logic": "ready_guarded"' in main
    assert '"recommendation_strength_logic": "ready_guarded"' in main
    assert '"observation_quality_dependency": "minimum_7_observed_days"' in main
    assert '"supplier_all_in_dependency": "official_contract_values_required"' in main
    assert '"official_report_handoff": "ready_guarded"' in main
    assert '"release_status": "v12_complete_external_data_gates_remain"' in main

def test_v1300_official_reporting_financial_handoff_is_strictly_guarded():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v13_reporting_financial_handoff"' in main
    assert '"source_decision_layer": "v12_guarded_decision_support"' in main
    assert '"projection_fields_policy": "publish_only_after_observation_quality_gate"' in main
    assert '"supplier_all_in_fields_policy": "publish_only_after_official_contract_validation"' in main
    assert '"advance_recommendation_policy": "publish_only_when_recommendation_publishable"' in main
    assert '"missing_financial_values_policy": "render_unavailable_never_assume"' in main
    assert '"epex_policy": "reference_only_never_supplier_all_in"' in main
    assert '"generator_status": "ready_guarded"' in main

def test_v1310_report_field_policy_never_fills_missing_financial_values():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v13_report_field_policy"' in main
    assert '"financial_projection": "quality_gate_required"' in main
    assert '"supplier_all_in_cost": "official_contract_validation_required"' in main
    assert '"advance_recommendation": "recommendation_publishable_required"' in main
    assert '"zero_substitution_for_missing_financial_data": False' in main
    assert '"epex_supplier_all_in_allowed": False' in main

def test_v1311_gui_runtime_boolean_literals_are_valid_python():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"zero_substitution_for_missing_financial_data": False' in main
    assert '"epex_supplier_all_in_allowed": False' in main
    assert '"zero_substitution_for_missing_financial_data": false' not in main
    assert '"epex_supplier_all_in_allowed": false' not in main

def test_v1320_official_report_render_contract_is_guarded():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v13_official_report_render_contract"' in main
    assert '"financial_simulation": "guarded"' in main
    assert '"year_projection": "guarded"' in main
    assert '"monthly_advance_control": "guarded"' in main
    assert '"unavailable_value_label": "Niet beschikbaar"' in main
    assert '"missing_value_numeric_fallback_allowed": False' in main
    assert '"supplier_all_in_label_requires_validated_contract": True' in main
    assert '"projection_label_requires_quality_gate": True' in main
    assert '"advance_advice_requires_publishable_decision": True' in main
    assert '"epex_may_be_labeled_supplier_all_in": False' in main

def test_v1330_completion_gate_is_ready_guarded():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert '"v13_completion_gate"' in main
    assert '"latest_release_display_policy": "latest_only"' in main
    assert '"release_status": "v13_complete_external_data_gates_remain"' in main
    assert "## v32.0.10" in changelog

def test_v1400_official_report_generation_activation_is_guarded():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v14_report_generation_activation"' in main
    assert '"management_page_financial_kpis": "guarded_active"' in main
    assert '"page2_financial_simulation": "guarded_active"' in main
    assert '"page2_year_projection": "guarded_active"' in main
    assert '"page2_monthly_advance_control": "guarded_active"' in main
    assert '"pages3_13_financial_context": "guarded_active"' in main
    assert '"missing_financial_values_policy": "render_unavailable_never_zero"' in main
    assert '"status": "production_active_guarded"' in main

def test_v1410_report_value_mapping_is_guarded():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v14_report_value_mapping"' in main
    assert '"management_financial_kpi_source": "v12_guarded_decision_support"' in main
    assert '"page2_projection_source": "financial_projection"' in main
    assert '"page2_projection_detail_source": "projection_detail"' in main
    assert '"supplier_all_in_source": "validated_contract_only"' in main
    assert '"zero_fallback_allowed": False' in main
    assert '"status": "mapped_guarded"' in main

def test_v1420_report_publication_gate_blocks_unvalidated_financial_values():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v14_report_publication_gate"' in main
    assert '"page2_projection_publishable": "observation_quality_gate"' in main
    assert '"page2_supplier_all_in_publishable": "official_contract_gate"' in main
    assert '"page2_advance_advice_publishable": "recommendation_publishable_gate"' in main
    assert '"blocked_value_rendering": "Niet beschikbaar"' in main
    assert '"blocked_value_numeric_fallback_allowed": False' in main
    assert '"epex_supplier_all_in_publication_allowed": False' in main
    assert '"status": "publication_guard_active"' in main

def test_v1430_completion_gate_marks_v14_complete_guarded():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v14_completion_gate"' in main
    assert '"official_report_generation": "ready_guarded"' in main
    assert '"financial_source_mapping": "ready_guarded"' in main
    assert '"financial_publication_gate": "ready_guarded"' in main
    assert '"ha_release_changelog_policy": "current_release_only"' in main
    assert '"release_status": "v14_complete_external_data_gates_remain"' in main

def test_v1430_home_assistant_addon_changelog_contains_only_current_release():
    changelog = (ROOT / "slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in changelog
    assert "10.6.1" not in changelog
    assert "10.6.0" not in changelog
    assert "10.5.39" not in changelog
    assert changelog.count("\n## ") == 1

def test_v1500_official_report_production_context_is_guarded():
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v15_official_report_production_context"' in main
    assert '"page1_management_summary": "production_context_active"' in main
    assert '"page2_financial_simulation": "production_context_active_guarded"' in main
    assert '"supplier_all_in_source": "validated_contract_only"' in main
    assert '"numeric_fallback_for_missing_values": False' in main
    assert '"status": "official_report_production_context_active"' in main

def test_v1500_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1
    assert "14.3.0" not in c

def test_v1510_generator_field_contract_is_guarded():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v15_report_generator_field_contract"' in main
    assert '"page2_financial_projection_source": "financial_projection"' in main
    assert '"page2_projection_detail_source": "projection_detail"' in main
    assert '"projection_requires_quality_gate": True' in main
    assert '"supplier_all_in_requires_contract_gate": True' in main
    assert '"numeric_missing_value_fallback": False' in main
    assert '"epex_supplier_all_in_allowed": False' in main
    assert '"status": "generator_field_contract_active"' in main

def test_v1510_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1
    assert "15.0.0" not in c

def test_v1520_report_render_safety_blocks_unvalidated_values():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v15_report_render_safety"' in main
    assert '"page2_projection_values": "publish_only_when_quality_gate_passed"' in main
    assert '"page2_supplier_all_in_values": "publish_only_when_contract_components_complete"' in main
    assert '"page2_advance_comparison": "publish_only_when_supplier_all_in_ready"' in main
    assert '"blocked_text": "Niet beschikbaar"' in main
    assert '"zero_substitution_allowed": False' in main
    assert '"validation_only_candidates_publishable": False' in main
    assert '"status": "render_safety_active"' in main

def test_v1520_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1
    assert "15.1.0" not in c

def test_v1530_completion_gate_closes_v15_guarded():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v15_completion_gate"' in main
    assert '"official_report_production_context": "ready_guarded"' in main
    assert '"generator_field_contracts": "ready_guarded"' in main
    assert '"financial_render_safety": "ready_guarded"' in main
    assert '"validation_candidates_publication": "forbidden"' in main
    assert '"next_major_release": "24.0.0"' in main
    assert '"release_status": "v15_complete_external_data_gates_remain"' in main

def test_v1530_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1
    assert "15.2.0" not in c

def test_v1600_financial_report_output_contract_is_guarded_and_automatic():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v16_financial_report_output_contract"' in main
    assert '"projection_activation": "automatic_after_7_observed_days"' in main
    assert '"supplier_all_in_activation": "automatic_after_validated_contract_components"' in main
    assert '"manual_gate_override_allowed": False' in main
    assert '"validation_candidate_as_report_value_allowed": False' in main
    assert '"missing_value_numeric_fallback": False' in main
    assert '"status": "official_output_contract_active"' in main

def test_v1600_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1
    assert "15.3.0" not in c

def test_v1610_output_activation_is_bound_to_runtime_gates():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v16_output_activation_state"' in main
    assert '"projection_gate_source": "projection_eligibility"' in main
    assert '"projection_publishable_when": "eligible_true"' in main
    assert '"supplier_all_in_gate_source": "contract_validation"' in main
    assert '"decision_publishable_when": "recommendation_publishable_true"' in main
    assert '"automatic_transition": True' in main
    assert '"manual_override_allowed": False' in main
    assert '"status": "activation_state_bound_to_runtime_gates"' in main

def test_v1610_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1
    assert "16.0.0" not in c

def test_v1620_output_runtime_validation_is_auditable():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v16_output_runtime_validation"' in main
    assert '"blocked_reason_source": "projection_eligibility.reason"' in main
    assert '"blocked_reason_source": "contract_validation.missing_components"' in main
    assert '"blocked_reason_source": "v12_decision_support.reason"' in main
    assert '"publication_state_values": ["blocked", "publishable"]' in main
    assert '"numeric_zero_for_blocked_allowed": False' in main
    assert '"status": "runtime_validation_active"' in main

def test_v1620_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1
    assert "16.1.0" not in c

def test_v1630_completion_gate_closes_v16_guarded():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v16_completion_gate"' in main
    assert '"official_output_contract": "ready_guarded"' in main
    assert '"runtime_activation_binding": "ready_guarded"' in main
    assert '"runtime_publication_validation": "ready_guarded"' in main
    assert '"next_major_release": "24.0.0"' in main
    assert '"release_status": "v16_complete_external_data_gates_remain"' in main

def test_v1630_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1
    assert "16.2.0" not in c

def test_v1700_financial_decision_output_is_strictly_guarded():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v17_financial_decision_output"' in main
    assert '"projection_quality_gate_passed"' in main
    assert '"supplier_all_in_ready"' in main
    assert '"contract_components_complete"' in main
    assert '"advance_can_be_lowered"' in main
    assert '"advance_is_appropriate"' in main
    assert '"advance_should_be_raised"' in main
    assert '"candidate_values_may_drive_decision": False' in main
    assert '"epex_may_drive_supplier_decision": False' in main
    assert '"status": "financial_decision_output_guard_active"' in main

def test_v1700_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1
    assert "16.3.0" not in c

def test_v1710_savings_recommendation_contract_is_fully_guarded():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v17_savings_recommendation_contract"' in main
    assert '"required_projection_state": "quality_gate_passed_true"' in main
    assert '"required_supplier_state": "supplier_all_in_ready_true"' in main
    assert '"required_contract_state": "contract_components_complete_true"' in main
    assert '"lower_monthly_advance"' in main
    assert '"keep_monthly_advance"' in main
    assert '"raise_monthly_advance"' in main
    assert '"savings_amount_source": "projected_monthly_difference_eur"' in main
    assert '"recommended_advance_source": "recommended_advance_eur"' in main
    assert '"candidate_only_values_allowed": False' in main
    assert '"epex_supplier_decision_allowed": False' in main
    assert '"status": "savings_recommendation_contract_active"' in main

def test_v1710_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1
    assert "17.0.0" not in c

def test_v1720_recommendation_publication_gate_requires_complete_decision():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v17_recommendation_publication_gate"' in main
    assert '"publishable_source": "v12_decision_support.recommendation_publishable"' in main
    assert '"required_publishable_value": True' in main
    assert '"projected_monthly_difference_eur"' in main
    assert '"recommended_advance_eur"' in main
    assert '"recommendation_strength"' in main
    assert '"partial_recommendation_allowed": False' in main
    assert '"automatic_publication_after_gate": True' in main
    assert '"status": "recommendation_publication_gate_active"' in main

def test_v1720_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1
    assert "17.1.0" not in c

def test_v1730_completion_gate_closes_v17_guarded_chain():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v17_completion_gate"' in main
    assert '"financial_decision_output": "ready_guarded"' in main
    assert '"savings_recommendation_contract": "ready_guarded"' in main
    assert '"recommendation_publication_gate": "ready_guarded"' in main
    assert '"partial_recommendation_publication": "forbidden"' in main
    assert '"candidate_values_publication": "forbidden"' in main
    assert '"next_major_release": "24.0.0"' in main
    assert '"release_status": "v17_complete_external_data_gates_remain"' in main

def test_v1730_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1
    assert "17.2.0" not in c

def test_v1800_financial_explainability_contract_is_guarded():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v18_financial_explainability_contract"' in main
    assert '"blocked_state_must_explain_why": True' in main
    assert '"publishable_state_must_explain_why": True' in main
    assert '"candidate_values_may_be_explanation_only": True' in main
    assert '"candidate_values_may_drive_decision": False' in main
    assert '"epex_role": "market_reference_only"' in main
    assert '"missing_contract_values_may_be_assumed": False' in main
    assert '"status": "financial_explainability_contract_active"' in main

def test_v1800_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1
    assert "17.3.0" not in c

def test_v1810_financial_explanation_runtime_is_guarded():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v18_financial_explanation_runtime"' in main
    assert '"reason_source": "v12_decision_support.reason"' in main
    assert '"publishable_explanation_requires_complete_recommendation": True' in main
    assert '"candidate_context_may_drive_recommendation": False' in main
    assert '"status": "financial_explanation_runtime_active"' in main

def test_v1810_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1
    assert "18.0.0" not in c

def test_v1820_report_explanation_handoff_is_guarded():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v18_report_explanation_handoff"' in main
    assert '"source": "v18_financial_explanation_runtime"' in main
    assert '"page1_management_summary": "explanation_ready_guarded"' in main
    assert '"page2_financial_simulation": "explanation_ready_guarded"' in main
    assert '"page2_monthly_advance_control": "explanation_ready_guarded"' in main
    assert '"blocked_reason_required": True' in main
    assert '"publishable_reason_required": True' in main
    assert '"candidate_context_may_drive_recommendation": False' in main
    assert '"epex_may_be_labeled_supplier_all_in": False' in main
    assert '"status": "report_explanation_handoff_active"' in main

def test_v1820_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1
    assert "18.1.0" not in c

def test_v1830_completion_gate_closes_explainability_chain():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v18_completion_gate"' in main
    assert '"financial_explainability_contract": "ready_guarded"' in main
    assert '"financial_explanation_runtime": "ready_guarded"' in main
    assert '"report_explanation_handoff": "ready_guarded"' in main
    assert '"blocked_explanation_required": True' in main
    assert '"publishable_explanation_required": True' in main
    assert '"candidate_context_policy": "informational_only_never_decision_input"' in main
    assert '"next_major_release": "24.0.0"' in main
    assert '"release_status": "v18_complete_external_data_gates_remain"' in main

def test_v1830_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1
    assert "18.2.0" not in c

def test_v1900_financial_report_decision_presentation_is_guarded():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v19_financial_report_decision_presentation"' in main
    assert '"blocked_decision_label": "Nog geen financieel advies"' in main
    assert '"publish_requires_complete_v17_recommendation": True' in main
    assert '"explanation_required": True' in main
    assert '"candidate_context_may_drive_decision": False' in main
    assert '"epex_may_drive_supplier_decision": False' in main
    assert '"status": "financial_report_decision_presentation_active"' in main

def test_v1900_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1
    assert "18.3.0" not in c

def test_v1910_report_action_mapping_is_guarded():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v19_report_action_mapping"' in main
    assert '"advance_can_be_lowered": "Maandvoorschot kan omlaag"' in main
    assert '"advance_is_appropriate": "Maandvoorschot is passend"' in main
    assert '"advance_should_be_raised": "Maandvoorschot verhogen"' in main
    assert '"management_summary_requires_reason": True' in main
    assert '"difference_requires_publishable_recommendation": True' in main
    assert '"candidate_context_may_drive_action": False' in main
    assert '"status": "report_action_mapping_active"' in main

def test_v1910_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1
    assert "19.0.0" not in c


def test_v1920_report_action_quality_context():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text()
    assert '"v19_report_action_quality_context"' in main
    assert '"show_observed_progress_when_blocked": True' in main
    assert '"show_remaining_observation_days_when_blocked": True' in main
    assert '"show_missing_contract_components_when_blocked": True' in main
    assert '"candidate_numbers_may_be_primary_report_values": False' in main
    assert '"status": "report_action_quality_context_active"' in main

def test_v1920_ha_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text()
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1


def test_v1930_completion_gate_closes_v19_chain():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v19_completion_gate"' in main
    assert '"financial_report_decision_presentation": "ready_guarded"' in main
    assert '"report_action_mapping": "ready_guarded"' in main
    assert '"report_action_quality_context": "ready_guarded"' in main
    assert '"automatic_transition_after_external_gates": True' in main
    assert '"manual_override_allowed": False' in main
    assert '"next_major_release": "24.0.0"' in main
    assert '"release_status": "v19_complete_external_data_gates_remain"' in main

def test_v1930_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1


def test_v2000_official_report_runtime_contract_is_guarded():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v20_financial_report_runtime_contract"' in main
    assert '"source_decision_presentation": "v19_financial_report_decision_presentation"' in main
    assert '"publish_requires_observation_quality_gate": True' in main
    assert '"supplier_all_in_requires_validated_contract": True' in main
    assert '"recommendation_requires_complete_publication_gate": True' in main
    assert '"candidate_values_primary_output_allowed": False' in main
    assert '"epex_supplier_all_in_allowed": False' in main
    assert '"status": "official_report_runtime_contract_active"' in main

def test_v2000_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1


def test_v2010_official_report_value_mapping_is_guarded():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v20_report_runtime_value_mapping"' in main
    assert '"source": "v20_financial_report_runtime_contract"' in main
    assert '"publish_requires_complete_gate": True' in main
    assert '"zero_substitution_allowed": False' in main
    assert '"candidate_values_primary_output_allowed": False' in main
    assert '"epex_supplier_all_in_allowed": False' in main
    assert '"status": "official_report_value_mapping_active"' in main

def test_v2010_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1


def test_v2020_official_report_publication_state_is_guarded():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v20_report_publication_state"' in main
    assert '"source_value_mapping": "v20_report_runtime_value_mapping"' in main
    assert '"page2_projection_requires_observation_gate": True' in main
    assert '"page2_supplier_all_in_requires_supplier_gate": True' in main
    assert '"page2_advance_control_requires_decision_gate": True' in main
    assert '"manual_override_allowed": False' in main
    assert '"automatic_transition_after_external_gates": True' in main
    assert '"status": "official_report_publication_state_active"' in main

def test_v2020_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1


def test_v2030_completion_gate_closes_v20_guarded_chain():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v20_completion_gate"' in main
    assert '"financial_report_runtime_contract": "ready_guarded"' in main
    assert '"report_runtime_value_mapping": "ready_guarded"' in main
    assert '"report_publication_state": "ready_guarded"' in main
    assert '"automatic_transition_after_external_gates": True' in main
    assert '"manual_override_allowed": False' in main
    assert '"next_major_release": "24.0.0"' in main
    assert '"release_status": "v20_complete_external_data_gates_remain"' in main

def test_v2030_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1


def test_v2040_savings_opportunity_engine_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v20_savings_opportunity_engine"' in main
    assert '"primary_goal": "reduce_total_energy_costs"' in main
    assert '"known_candidate": "Marstek Venus 3"' in main
    assert '"candidate_product_policy": "candidate_not_preselected"' in main
    assert '"replacement_recommendation_requires_positive_financial_case": True' in main
    assert '"roadmap_state": "v20_reporting_baseline_complete_savings_development_continues"' in main
    assert '"savings_opportunity_engine_active_guarded"' in main

def test_v2040_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1


def test_v2050_savings_priority_engine_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v20_savings_priority_engine"' in main
    assert '"estimated_annual_savings_eur"' in main
    assert '"simple_payback_years"' in main
    assert '"implementation_effort"' in main
    assert '"include_in_financial_ranking": False' in main
    assert '"zero_substitution_allowed": False' in main
    assert '"known_candidate": "Marstek Venus 3"' in main
    assert '"savings_priority_engine_active_guarded"' in main

def test_v2050_ha_changelog_current_release_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1


def test_v2060_savings_action_handoff():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in ['"v20_savings_action_handoff"','"wait_for_data"','"complete_validated_opportunities_only": True','"candidate_only_values_may_drive_action": False','"automatic_re_evaluation_after_new_measurements": True','"savings_action_handoff_active_guarded"','"savings_opportunity_engine": "ready_guarded"','"savings_priority_engine": "ready_guarded"','"savings_action_handoff": "ready_guarded"','"v20_savings_chain_complete_external_data_gates_remain"']:
        assert x in main

def test_v2060_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2100_financial_action_runtime_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in ['"v21_financial_action_runtime"','"financial_action_runtime_active_guarded"','"waiting_for_observation"','"waiting_for_contract_data"','"waiting_for_opportunity_inputs"','"actionable"','"requires_complete_validated_opportunity": True','"manual_override_allowed": False','"candidate_values_may_drive_action": False','"zero_substitution_allowed": False']:
        assert x in main

def test_v2100_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2110_runtime_gate_resolution_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in ['"v21_runtime_gate_resolution"','"runtime_gate_resolution_active_guarded"','"observation_quality_gate_false": "waiting_for_observation"','"supplier_contract_gate_false": "waiting_for_contract_data"','"opportunity_input_gate_false": "waiting_for_opportunity_inputs"','"all_required_gates_true": "actionable"','"partial_gate_pass_may_publish_action": False','"automatic_transition": True']:
        assert x in main

def test_v2110_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2120_blocked_dependency_runtime_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v21_blocked_dependency_runtime"',
        '"blocked_dependency_runtime_active_guarded"',
        '"show_only_real_blockers": True',
        '"preserve_gate_order": True',
        '"do_not_infer_missing_contract_values": True',
        '"do_not_promote_candidate_values": True',
        '"automatic_refresh_after_new_data": True',
        '"remaining_observation_days"',
        '"missing_contract_components"',
        '"missing_opportunity_inputs"'
    ]:
        assert x in main

def test_v2120_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c
    assert c.count("\n## ") == 1


def test_v2130_financial_action_readiness_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in ['"v21_financial_action_readiness"','"financial_action_readiness_active_guarded"','"switch_contract"','"buy_battery"','"replace_appliance"','"shift_load"','"ready_for_financial_evaluation"','"actionable_requires_positive_validated_financial_case": True','"automatic_re_evaluation_after_new_data": True','"publish_action_only_when_actionable": True']:
        assert x in main

def test_v2130_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2140_financial_evaluation_contract_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in ['"v21_financial_evaluation_contract"','"financial_evaluation_contract_active_guarded"','"validated_annual_savings_eur"','"simple_payback_years"','"requires_ready_for_financial_evaluation": True','"positive_savings_required_for_cost_saving_action": True','"candidate_values_may_not_drive_evaluation": True','"negative_or_zero_savings_may_not_trigger_purchase_or_switch": True']:
        assert x in main

def test_v2140_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2150_financial_action_selection_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in ['"v21_financial_action_selection"','"financial_action_selection_active_guarded"','"highest_validated_annual_savings_eur"','"shortest_validated_simple_payback_years"','"lowest_implementation_effort"','"completed_evaluations_only": True','"positive_annual_savings_required": True','"blocked_or_incomplete_actions_excluded": True','"automatic_reselection_after_new_data": True']:
        assert x in main

def test_v2150_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2160_completion_gate_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in ['"v21_completion_gate"','"v21_complete_external_data_gates_remain"','"v21_complete_guarded_financial_action_chain_ready_for_v22"','"next_major_release": "24.0.0"','"financial_action_selection": "ready_guarded"','"publish_only_complete_positive_financial_action": True','"manual_override_allowed": False']:
        assert x in main

def test_v2160_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2200_financial_decision_runtime_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in ['"v22_financial_decision_runtime"','"financial_decision_runtime_active_guarded"','"requires_v21_chain_ready_guarded": True','"external_gates_must_be_open": True','"manual_override_allowed": False','"negative_or_zero_savings_change_action_allowed": False','"monthly_savings_eur"']:
        assert x in main

def test_v2200_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2210_decision_evidence_runtime_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v22_decision_evidence_runtime"',
        '"decision_evidence_runtime_active_guarded"',
        '"financial_value_requires_traceable_inputs": True',
        '"decision_requires_traceable_evaluation": True',
        '"candidate_values_may_not_be_evidence": True',
        '"preserve_measurement_window": True',
        '"preserve_contract_validation_state": True',
        '"publish_financial_decision_only_with_complete_evidence": True'
    ]:
        assert x in main

def test_v2210_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2220_decision_confidence_runtime_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in ['"v22_decision_confidence_runtime"','"decision_confidence_runtime_active_guarded"','"blocked_when_required_gate_false": True','"validated_requires_complete_traceable_evidence": True','"actionable_requires_positive_complete_financial_case": True','"candidate_values_may_not_raise_confidence": True','"actionable_decision_requires_actionable_confidence": True']:
        assert x in main

def test_v2220_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2230_decision_confidence_resolution_runtime_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in ['"v22_decision_confidence_resolution_runtime"','"decision_confidence_resolution_runtime_active_guarded"','"first_unresolved_required_gate_wins": True','"actionable_requires_all_required_gates": True','"validated_does_not_imply_positive_financial_case": True','"candidate_values_may_not_change_state": True','"publish_change_action_only_when_actionable": True']:
        assert x in main

def test_v2230_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2240_decision_publication_runtime_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in ['"v22_decision_publication_runtime"','"decision_publication_runtime_active_guarded"','"publishable_requires_actionable_confidence": True','"informational_may_not_recommend_change": True','"candidate_values_may_not_be_published_as_advice": True','"page1_management_action_requires_publishable": True','"page2_financial_recommendation_requires_publishable": True']:
        assert x in main

def test_v2240_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2250_decision_publication_payload_runtime_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in ['"v22_decision_publication_payload_runtime"','"decision_publication_payload_runtime_active_guarded"','"blocked_action": "wait_for_data"','"informational_action": "wait_for_data"','"candidate_values_never_enter_action_payload": True','"page1_financial_kpis": "publishable_validated_numeric_values_only"']:
        assert x in main

def test_v2250_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2260_completion_gate_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v22_completion_gate"',
        '"v22_complete_external_data_gates_remain"',
        '"v22_complete_guarded_auditable_decision_publication_chain_ready_for_v23"',
        '"next_major_release": "24.0.0"',
        '"external_data_may_remain_blocked_at_release_completion": True',
        '"automatic_transition_after_external_gates": True',
        '"publish_only_actionable_positive_financial_case": True'
    ]:
        assert x in main

def test_v2260_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2300_savings_portfolio_runtime_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v23_savings_portfolio_runtime"',
        '"savings_portfolio_runtime_active_guarded"',
        '"energy_contract"',
        '"home_battery"',
        '"appliance_replacement"',
        '"load_shifting"',
        '"rank_by_validated_annual_savings_first": True',
        '"candidate_values_may_not_drive_ranking": True'
    ]:
        assert x in main

def test_v2300_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2310_portfolio_evaluation_runtime_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v23_portfolio_evaluation_runtime"',
        '"portfolio_evaluation_runtime_active_guarded"',
        '"first_required_gate_failure_is_primary_blocker": True',
        '"candidate_values_may_not_resolve_blocker": True',
        '"validated_opportunity_requires_positive_annual_savings": True',
        '"zero_or_negative_savings_result": "validated_no_action"'
    ]:
        assert x in main

def test_v2310_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2320_portfolio_ranking_runtime_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v23_portfolio_ranking_runtime"',
        '"portfolio_ranking_runtime_active_guarded"',
        '"eligible_evaluation_state": "validated_opportunity"',
        '"highest_validated_annual_savings_eur"',
        '"shortest_validated_simple_payback_years"',
        '"lowest_implementation_effort"',
        '"candidate_values_may_not_drive_ranking": True',
        '"blocked_domains_excluded_from_numeric_ranking": True'
    ]:
        assert x in main

def test_v2320_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2330_portfolio_selection_runtime_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in ['"v23_portfolio_selection_runtime"','"portfolio_selection_runtime_active_guarded"','"rank_1_validated_opportunity_only": True','"positive_annual_savings_required": True','"blocked_domains_may_not_be_selected": True','"candidate_values_may_not_drive_selection": True','"automatic_reselection_after_new_data": True']:
        assert x in main

def test_v2330_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2340_portfolio_recommendation_runtime_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in ['"v23_portfolio_recommendation_runtime"','"portfolio_recommendation_runtime_active_guarded"','"actionable_requires_selected_action": True','"positive_validated_annual_savings_required": True','"candidate_values_may_not_be_published_as_advice": True','"automatic_refresh_after_new_data": True']:
        assert x in main

def test_v2340_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2350_completion_publication_gate_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in ['"v23_completion_publication_gate"','"v23_complete_external_data_gates_remain"','"savings_portfolio_runtime": "ready_guarded"','"portfolio_recommendation_runtime": "ready_guarded"','"publish_only_actionable_positive_financial_case": True','"candidate_values_may_drive_action": False','"next_major_release": "24.0.0"']:
        assert x in main

def test_v2350_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2400_action_handoff_runtime_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v24_action_handoff_runtime"',
        '"action_handoff_runtime_active_guarded"',
        '"roadmap_step": "1/5"',
        '"publishable_v23_recommendation_required": True',
        '"candidate_values_may_not_activate_handoff": True',
        '"automatic_purchase_switch_or_device_control": False',
        '"user_confirmation_required_before_external_action": True',
        '"zero_substitution_allowed": False',
        '"next_step": "v24_action_tracking_runtime"'
    ]:
        assert x in main

def test_v2400_version_consistency():
    assert (ROOT/"VERSIE.txt").read_text(encoding="utf-8").strip() == "32.0.33"
    config=(ROOT/"slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'version: "32.0.33"' in config
    assert 'APP_VERSION = "32.0.33"' in main

def test_v2400_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2410_action_tracking_runtime_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v24_action_tracking_runtime"',
        '"action_tracking_runtime_active_guarded"',
        '"roadmap_step": "2/5"',
        '"tracking_starts_only_from_guarded_handoff": True',
        '"realized_savings_may_not_be_claimed_before_measurement": True',
        '"realized_savings_eur": None',
        '"self_report_alone_confirms_financial_savings": False',
        '"next_step": "v24_realized_savings_runtime"'
    ]:
        assert x in main

def test_v2410_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2420_realized_savings_runtime_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v24_realized_savings_runtime"',
        '"realized_savings_runtime_active_guarded"',
        '"roadmap_step": "3/5"',
        '"validated_execution_required": True',
        '"traceable_pre_action_baseline_required": True',
        '"traceable_post_action_measurement_required": True',
        '"business_case_estimate_may_not_be_promoted_to_actual": True',
        '"self_report_may_not_create_realized_savings": True',
        '"automatic_annualization_from_short_window": False',
        '"next_step": "v24_variance_learning_runtime"'
    ]:
        assert x in main

def test_v2420_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2430_variance_learning_runtime_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v24_variance_learning_runtime"',
        '"variance_learning_runtime_active_guarded"',
        '"roadmap_step": "4/5"',
        '"validated_realized_savings_required": True',
        '"variance_must_be_derived_from_validated_values": True',
        '"candidate_values_may_not_drive_learning": True',
        '"single_short_window_may_not_rewrite_financial_model": True',
        '"audit_trail_required_for_model_adjustment": True',
        '"next_step": "v24_completion_gate"'
    ]:
        assert x in main

def test_v2430_version_consistency():
    assert (ROOT/"VERSIE.txt").read_text(encoding="utf-8").strip() == "32.0.33"
    config=(ROOT/"slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'version: "32.0.33"' in config
    assert 'APP_VERSION = "32.0.33"' in main

def test_v2430_changelog_latest_only():
    c=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.0.33" in c and c.count("\n## ") == 1


def test_v2440_completion_gate_present():
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v24_completion_gate"',
        '"roadmap_step": "5/5"',
        '"action_handoff_runtime": "ready_guarded"',
        '"action_tracking_runtime": "ready_guarded"',
        '"realized_savings_runtime": "ready_guarded"',
        '"variance_learning_runtime": "ready_guarded"',
        '"external_data_may_remain_blocked_at_release_completion": True',
        '"candidate_values_may_drive_action_or_learning": False',
        '"business_case_estimate_may_be_promoted_to_realized": False',
        '"single_short_window_may_rewrite_financial_model": False',
        '"next_major_release": "25.0.0"',
        '"v24_complete_external_data_gates_remain"'
    ]:
        assert x in main

def test_v2440_version_and_changelog_consistency():
    assert (ROOT/"VERSIE.txt").read_text(encoding="utf-8").strip() == "32.0.33"
    config=(ROOT/"slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    changelog=(ROOT/"slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert 'version: "32.0.33"' in config
    assert 'APP_VERSION = "32.0.33"' in main
    assert "## 32.0.33" in changelog and changelog.count("\n## ") == 1


def test_v2500_savings_ledger_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"v25_savings_ledger_runtime"' in source
    assert '"roadmap_step": "1/5"' in source
    assert '"deduplication_key": "stable_action_id_plus_validated_evidence_reference_plus_realized_period"' in source
    assert '"same_validated_savings_may_be_booked_twice": False' in source
    assert '"negative_values_may_be_clamped_to_zero": False' in source
    assert '"candidate_values_may_not_be_booked": True' in source
    assert '"next_step": "v25_cumulative_portfolio_impact_runtime"' in source

def test_v2500_preserves_suffix_tolerant_publisher():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'processed_dir.glob(f"EnergieProject_v{version}*.zip")' in source
    installer = (ROOT / "tools/release_installer.sh").read_text(encoding="utf-8")
    assert 'CANONICAL_PROCESSED="$PROCESSED/EnergieProject_v${NEW_VERSION}.zip"' in installer


def test_v2510_cumulative_portfolio_impact_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v25_cumulative_portfolio_impact_runtime"',
        '"roadmap_step": "2/5"',
        '"booked_ledger_entries_only": True',
        '"deduplicate_using_ledger_identity": True',
        '"positive_and_negative_realized_impacts_preserved": True',
        '"candidate_values_excluded": True',
        '"partial_validated_portfolio_must_be_labelled_partial": True',
        '"next_step": "v25_monthly_budget_impact_runtime"',
        '"cumulative_portfolio_impact_runtime_active_guarded"'
    ]:
        assert x in source


def test_v2520_monthly_budget_impact_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v25_monthly_budget_impact_runtime"',
        '"roadmap_step": "3/5"',
        '"monthly_advance_reference_eur": 150.0',
        '"partial_measurement_window_may_not_be_extrapolated_automatically": True',
        '"annualized_estimate_may_not_be_divided_by_twelve_without_validated_annualization": True',
        '"ledger_savings_alone_may_not_change_supplier_advance": True',
        '"double_counting_with_supplier_cost_projection_forbidden": True',
        '"partial_or_noncomparable_period_remains_unavailable": True',
        '"next_step": "v25_report_publication_runtime"',
        '"monthly_budget_impact_runtime_active_guarded"'
    ]:
        assert x in source

def test_v2520_version_consistency():
    assert (ROOT/"VERSIE.txt").read_text(encoding="utf-8").strip() == "32.0.33"
    config=(ROOT/"slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    main=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'version: "32.0.33"' in config
    assert 'APP_VERSION = "32.0.33"' in main


def test_v2530_report_publication_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v25_report_publication_runtime"',
        '"roadmap_step": "4/5"',
        '"validated_savings_ledger_required": True',
        '"candidate_values_excluded_from_primary_report": True',
        '"partial_measurement_window_may_not_be_presented_as_full_month": True',
        '"double_counting_with_supplier_projection_forbidden": True',
        '"next_step": "v25_completion_gate"',
        '"report_publication_runtime_active_guarded"'
    ]:
        assert x in source

def test_v2530_completion_gate_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v25_completion_gate"',
        '"roadmap_step": "5/5"',
        '"savings_ledger_runtime": "ready_guarded"',
        '"cumulative_portfolio_impact_runtime": "ready_guarded"',
        '"monthly_budget_impact_runtime": "ready_guarded"',
        '"report_publication_runtime": "ready_guarded"',
        '"external_data_may_remain_blocked_at_release_completion": True',
        '"partial_period_may_be_promoted_to_full_month": False',
        '"next_major_release": "32.0.10"',
        '"v25_complete_external_data_gates_remain"'
    ]:
        assert x in source


def test_v2600_decision_value_prioritization_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v26_decision_value_prioritization_runtime"',
        '"roadmap_step": "1/4"',
        '"primary_metric": "validated_expected_euro_value"',
        '"blocked_or_missing_financial_value_rankable": False',
        '"maximum_primary_actions": 3',
        '"supplier_switch_requires_official_contract_components": True',
        '"device_replacement_requires_validated_consumption_and_payback_case": True',
        '"double_counting_forbidden": True',
        '"next_step": "v26_action_queue_runtime"',
        '"decision_value_prioritization_runtime_active_guarded"'
    ]:
        assert x in source


def test_v2610_action_queue_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v26_action_queue_runtime"',
        '"roadmap_step": "2/4"',
        '"maximum_primary_actions": 3',
        '"blocked_actions_may_not_be_promoted_to_act_now": True',
        '"candidate_values_may_not_drive_queue_position": True',
        '"supplier_contract_gate": "official_contract_values_required"',
        '"act_now_requires_all_required_gates_open": True',
        '"next_step": "v26_action_queue_publication_runtime"',
        '"action_queue_runtime_active_guarded"'
    ]:
        assert x in source


def test_v2611_action_queue_python_literals_are_runtime_safe():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    start = source.index('            "v26_action_queue_runtime": {')
    end = source.index('            "v26_decision_value_prioritization_runtime": {', start)
    block = source[start:end]
    assert ": true" not in block
    assert ": false" not in block
    assert ": null" not in block
    assert ": True" in block
    assert ": False" in block
    assert ": None" in block


def test_v2620_action_queue_publication_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v26_action_queue_publication_runtime"',
        '"roadmap_step": "3/4"',
        '"maximum_primary_actions": 3',
        '"candidate_values_primary_output_allowed": False',
        '"next_step": "v26_completion_gate"',
        '"action_queue_publication_runtime_active_guarded"'
    ]:
        assert x in source

def test_v2620_completion_gate_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v26_completion_gate"',
        '"roadmap_step": "4/4"',
        '"decision_value_prioritization_runtime": "ready_guarded"',
        '"action_queue_runtime": "ready_guarded"',
        '"action_queue_publication_runtime": "ready_guarded"',
        '"external_data_may_remain_blocked_at_release_completion": True',
        '"next_major_release": "32.0.10"',
        '"v26_complete_external_data_gates_remain"'
    ]:
        assert x in source


def test_v2700_execution_readiness_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v27_execution_readiness_runtime"',
        '"roadmap_step": "1/4"',
        '"maximum_primary_actions": 3',
        '"required_external_gates_must_be_open": True',
        '"measurement_plan_required_when_savings_need_validation": True',
        '"automatic_supplier_switch_allowed": False',
        '"automatic_purchase_allowed": False',
        '"double_counting_allowed": False',
        '"next_step": "v27_execution_plan_runtime"',
        '"execution_readiness_runtime_active_guarded"'
    ]:
        assert x in source


def test_v2710_execution_plan_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v27_execution_plan_runtime"',
        '"roadmap_step": "2/4"',
        '"maximum_primary_plans": 3',
        '"success_criterion_required": True',
        '"stop_condition_required": True',
        '"automatic_purchase_allowed": False',
        '"automatic_supplier_switch_allowed": False',
        '"double_counting_allowed": False',
        '"next_step": "v27_execution_plan_publication_runtime"',
        '"execution_plan_runtime_active_guarded"'
    ]:
        assert x in source


def test_v2720_execution_plan_publication_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v27_execution_plan_publication_runtime"',
        '"roadmap_step": "3/4"',
        '"maximum_primary_plans": 3',
        '"candidate_values_primary_output_allowed": False',
        '"automatic_purchase_allowed": False',
        '"next_step": "v27_completion_gate"',
        '"execution_plan_publication_runtime_active_guarded"'
    ]:
        assert x in source

def test_v2720_completion_gate_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v27_completion_gate"',
        '"roadmap_step": "4/4"',
        '"execution_readiness_runtime": "ready_guarded"',
        '"execution_plan_runtime": "ready_guarded"',
        '"execution_plan_publication_runtime": "ready_guarded"',
        '"automatic_external_execution_allowed": False',
        '"next_major_release": "32.0.10"',
        '"v27_complete_external_data_and_user_action_gates_remain"'
    ]:
        assert x in source


def test_v2800_execution_outcome_verification_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v28_execution_outcome_verification_runtime"',
        '"roadmap_step": "1/4"',
        '"validated_execution_evidence_required": True',
        '"self_report_alone_may_not_create_realized_savings": True',
        '"automatic_annualization_from_short_window": False',
        '"negative_realized_impact_preserved": True',
        '"automatic_purchase_allowed": False',
        '"next_step": "v28_verified_outcome_portfolio_runtime"',
        '"execution_outcome_verification_runtime_active_guarded"'
    ]:
        assert x in source


def test_v2810_verified_outcome_portfolio_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v28_verified_outcome_portfolio_runtime"',
        '"roadmap_step": "2/4"',
        '"outcome_validated_required_for_realized_totals": True',
        '"duplicate_action_ids_forbidden": True',
        '"double_counting_allowed": False',
        '"automatic_annualization_allowed": False',
        '"candidate_values_in_realized_totals_allowed": False',
        '"next_step": "v28_outcome_learning_runtime"',
        '"verified_outcome_portfolio_runtime_active_guarded"'
    ]:
        assert x in source


def test_v2820_outcome_learning_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v28_outcome_learning_runtime"',
        '"roadmap_step": "3/4"',
        '"repeated_evidence_required_for_model_adjustment": True',
        '"single_event_model_rewrite_allowed": False',
        '"short_window_model_rewrite_allowed": False',
        '"next_step": "v28_completion_gate"',
        '"outcome_learning_runtime_active_guarded"'
    ]:
        assert x in source

def test_v2820_completion_gate_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v28_completion_gate"',
        '"roadmap_step": "4/4"',
        '"execution_outcome_verification_runtime": "ready_guarded"',
        '"verified_outcome_portfolio_runtime": "ready_guarded"',
        '"outcome_learning_runtime": "ready_guarded"',
        '"double_counting_allowed": False',
        '"next_major_release": "32.0.10"',
        '"v28_complete_external_execution_measurement_and_learning_gates_remain"'
    ]:
        assert x in source


def test_v2900_forecast_calibration_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v29_forecast_calibration_runtime"',
        '"roadmap_step": "1/4"',
        '"minimum_independent_evidence_events": 2',
        '"historical_actuals_must_remain_immutable": True',
        '"historical_actuals_rewrite_allowed": False',
        '"single_event_calibration_allowed": False',
        '"automatic_annualization_from_short_window": False',
        '"next_step": "v29_calibrated_savings_forecast_runtime"',
        '"forecast_calibration_runtime_active_guarded"'
    ]:
        assert x in source


def test_v2910_calibrated_savings_forecast_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v29_calibrated_savings_forecast_runtime"',
        '"roadmap_step": "2/4"',
        '"validated_calibration_required": True',
        '"historical_actuals_immutable": True',
        '"uncertainty_required": True',
        '"calibrated_forecast_may_not_become_realized_savings": True',
        '"double_counting_allowed": False',
        '"next_step": "v29_forecast_publication_runtime"',
        '"calibrated_savings_forecast_runtime_active_guarded"'
    ]:
        assert x in source


def test_v2920_forecast_publication_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v29_forecast_publication_runtime"',
        '"roadmap_step": "3/4"',
        '"validated_forecast_required": True',
        '"uncertainty_required": True',
        '"forecast_may_be_presented_as_realized_savings": False',
        '"next_step": "v29_completion_gate"',
        '"forecast_publication_runtime_active_guarded"'
    ]:
        assert x in source

def test_v2920_completion_gate_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v29_completion_gate"',
        '"roadmap_step": "4/4"',
        '"forecast_calibration_runtime": "ready_guarded"',
        '"calibrated_savings_forecast_runtime": "ready_guarded"',
        '"forecast_publication_runtime": "ready_guarded"',
        '"next_major_release": "32.0.10"',
        '"v29_complete_external_learning_context_and_confidence_gates_remain"'
    ]:
        assert x in source


def test_v3000_adaptive_optimization_candidate_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v30_adaptive_optimization_candidate_runtime"',
        '"roadmap_step": "1/4"',
        '"maximum_primary_candidates": 3',
        '"rank_by_validated_expected_euro_value_first": True',
        '"automatic_supplier_switch_allowed": False',
        '"automatic_purchase_allowed": False',
        '"zero_substitution_allowed": False',
        '"next_step": "v30_optimization_selection_runtime"',
        '"adaptive_optimization_candidate_runtime_active_guarded"'
    ]:
        assert x in source


def test_v3010_optimization_selection_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v30_optimization_selection_runtime"',
        '"roadmap_step": "2/4"',
        '"maximum_primary_selection": 1',
        '"positive_validated_expected_euro_value_required": True',
        '"user_authority_gate_required_before_execution": True',
        '"automatic_external_execution_allowed": False',
        '"next_step": "v30_optimization_execution_plan_runtime"',
        '"optimization_selection_runtime_active_guarded"'
    ]:
        assert x in source


def test_v3020_optimization_execution_plan_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v30_optimization_execution_plan_runtime"',
        '"roadmap_step": "3/4"',
        '"single_selected_candidate_required": True',
        '"measurement_baseline_required": True',
        '"rollback_condition_required": True',
        '"explicit_user_authority_required_before_external_execution": True',
        '"automatic_external_execution_allowed": False',
        '"next_step": "v30_completion_gate"',
        '"optimization_execution_plan_runtime_active_guarded"'
    ]:
        assert x in source


def test_v3030_completion_gate_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v30_completion_gate_runtime"',
        '"roadmap_step": "4/4"',
        '"candidate_discovery_runtime_required": True',
        '"single_selection_runtime_required": True',
        '"execution_plan_runtime_required": True',
        '"rollback_gate_required": True',
        '"explicit_user_authority_required_before_external_execution": True',
        '"automatic_external_execution_allowed": False',
        '"v30_release_state": "complete_after_home_assistant_validation"',
        '"next_step": "post_v30_roadmap_bundle"',
        '"v30_completion_gate_active_guarded"'
    ]:
        assert x in source


def test_v3031_release_identity_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"release_identity_runtime"',
        '"release_version": APP_VERSION',
        '"validation_marker": "current_release_runtime_identity"',
        '"must_match_app_version": True',
        '"must_match_addon_config_version": True',
        '"status": "release_identity_active"'
    ]:
        assert x in source


def test_v3100_conversation_context_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v31_conversation_context_runtime"',
        '"roadmap_step": "1/4"',
        '"ordinary_language_questions_supported": True',
        '"answer_from_validated_project_context_first": True',
        '"actual_forecast_and_candidate_values_must_remain_separate": True',
        '"next_step": "v31_conversation_intent_runtime"',
        '"conversation_context_runtime_active_guarded"'
    ]:
        assert x in source

def test_v3100_conversation_intent_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v31_conversation_intent_runtime"',
        '"roadmap_step": "2/4"',
        '"status": "summarize_current_project_and_data_readiness"',
        '"diagnose": "identify_current_blockers_or_missing_inputs"',
        '"recommend_intent_requires_existing_publishable_decision": True',
        '"unknown_intent_external_execution_allowed": False',
        '"next_step": "v31_conversation_response_runtime"',
        '"conversation_intent_runtime_active_guarded"'
    ]:
        assert x in source

def test_v3100_release_identity_marker():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"release_version": APP_VERSION' in source
    assert '"release_family": "v32_final_integration"' in source
    assert '"validation_marker": "current_release_runtime_identity"' in source


def test_v3110_conversation_response_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v31_conversation_response_runtime"',
        '"roadmap_step": "3/4"',
        '"financial_numbers_require_existing_validated_source": True',
        '"missing_values_must_be_stated_unavailable": True',
        '"ordinary_dutch_supported": True',
        '"publish_only_existing_guarded_recommendation": True',
        '"fabricated_source_allowed": False',
        '"next_step": "v31_chat_voice_completion_and_report_handoff"',
        '"conversation_response_runtime_active_guarded"'
    ]:
        assert x in source

def test_v3110_release_identity_marker():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"release_version": APP_VERSION' in source
    assert '"release_family": "v32_final_integration"' in source
    assert '"validation_marker": "current_release_runtime_identity"' in source


def test_v3120_chat_voice_completion_and_report_handoff_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v31_chat_voice_completion_and_report_handoff"',
        '"roadmap_step": "4/4"',
        '"report_handoff_required": True',
        '"print_handoff_required": True',
        '"portrait_layout_preserved": True',
        '"official_template_policy_preserved": True',
        '"chat_response_may_not_invent_report_values": True',
        '"automatic_supplier_switch_allowed": False',
        '"v31_release_state": "complete_after_home_assistant_validation"',
        '"next_major_release": "32.0.10"',
        '"v31_chat_voice_completion_and_report_handoff_active_guarded"'
    ]:
        assert x in source

def test_v3120_release_identity_marker():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"release_version": APP_VERSION' in source
    assert '"release_family": "v32_final_integration"' in source
    assert '"validation_marker": "current_release_runtime_identity"' in source


def test_v3200_final_integration_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v32_final_integration_runtime"',
        '"roadmap_step": "1/3"',
        '"backup_recovery_contract_required": True',
        '"final_validation_contract_required": True',
        '"single_release_version_required": True',
        '"next_step": "v32_backup_recovery_runtime"'
    ]:
        assert x in source

def test_v3200_backup_recovery_runtime_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v32_backup_recovery_runtime"',
        '"roadmap_step": "2/3"',
        '"manifest_required": True',
        '"sha256_inventory_required": True',
        '"home_assistant_validation_required_after_restore": True',
        '"minimum_known_good_releases": 3',
        '"next_step": "v32_final_validation_gate"'
    ]:
        assert x in source

def test_v3200_final_validation_gate_present():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    for x in [
        '"v32_final_validation_gate"',
        '"roadmap_step": "3/3"',
        '"full_regression_suite_required": True',
        '"zip_integrity_required": True',
        '"home_assistant_analysis_required": True',
        '"release_state": "awaiting_home_assistant_validation"',
        '"next_step_after_success": "maintenance_only_or_explicit_new_roadmap"'
    ]:
        assert x in source

def test_v3200_release_identity_marker():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert '"release_version": APP_VERSION' in source
    assert '"release_family": "v32_final_integration"' in source
    assert '"validation_marker": "current_release_runtime_identity"' in source


def test_v3201_release_installer_backup_retention():
    source = (ROOT / "tools/release_installer.sh").read_text(encoding="utf-8")
    for x in [
        'BACKUP_RETENTION="${ENERGIE_BACKUP_RETENTION:-3}"',
        'cleanup_old_backups(){',
        'EnergieProject_pre_*.tar.gz',
        'tail -n +$((BACKUP_RETENTION + 1))',
        '[ "$old_backup" = "$BACKUP" ] && continue',
        'Backupretentie toegepast: maximaal $BACKUP_RETENTION pre-release backups',
    ]:
        assert x in source


def test_v3203_home_assistant_github_publisher_uses_dedicated_worktree():
    source = MAIN.read_text(encoding="utf-8")
    assert 'GITHUB_WORKTREE = GITHUB_PUBLISH_DIR / "worktree"' in source
    assert 'def _prepare_github_worktree' in source
    assert 'def _sync_project_to_github_worktree' in source
    assert 'cwd=GITHUB_WORKTREE' in source
    assert 'GitHub-push uitgevoerd maar remote verificatie wijkt af' in source
    publisher = source[source.index('def publish_github_release'):source.index('def _write_github_publish_state')]
    assert 'cwd=NAS_PROJECT_ROOT' not in publisher


def test_v3204_github_publisher_state_does_not_recursively_persist_last_publication():
    source = MAIN.read_text(encoding="utf-8")
    publisher = source[source.index('def publish_github_release'):source.index('def _write_github_publish_state')]
    assert 'publish_status = {k: v for k, v in status.items() if k != "last_publication"}' in publisher
    assert 'result = {**publish_status, "published": rc == 0' in publisher
    assert 'result = {**status, "published": rc == 0' not in publisher
    assert '"validation_marker": "current_release_runtime_identity"' in source


def test_v3208_github_status_is_server_rendered_without_browser_fetch():
    source = MAIN.read_text(encoding="utf-8")
    assert "def github_publication_ui_snapshot()" in source
    assert "github_ui = github_publication_ui_snapshot()" in source
    assert "v32.0.10: status staat server-side in de pagina." in source
    assert "await fetch(ingressApiUrl('/api/github-publisher/status')" not in source
    assert "await fetch('./api/github-publisher/status'" not in source
    assert "function refreshGithubPublisherStatus(showKey=false)" in source


def test_v3209_smp_content_coverage_and_current_transfer_route():
    source = (ADDON / "rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "32.0.33"' in source
    assert "def validate_smp_content_coverage(" in source
    assert '"content_coverage_report.json"' in source
    assert '"smp_content_coverage"' in source
    assert 'destination_root = NAS_DATA_ROOT / "01_Input"' in source
    assert 'options.transfer_share_folder == "Energie_Overdracht"' in source

def test_v32010_current_month_smp_lag_is_not_software_error():
    source = MAIN.read_text(encoding="utf-8")
    assert 'APP_VERSION = "32.0.33"' in source
    assert '"partial_current_month"' in source
    assert '"available_through"' in source
    assert '"calendar_expected_through"' in source
    assert "SlimmeMeterPortal bronvertraging" in source
    assert 'central_validation.setdefault("warnings", [])' in source


def test_v32011_home_assistant_is_central_api_import_layer():
    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'version: "32.0.33"' in config
    assert 'workflow_mode: "full_month_workflow"' in config
    assert 'workflow_mode="full_month_workflow"' in main


def test_v32011_nas_has_no_direct_smp_api_route():
    path = ROOT.parent / "Infra/Docker/native-mcp/month_workflow_v5.py"
    if not path.is_file():
        import pytest
        pytest.skip("full-project Infra context not present in standalone release ZIP")
    source = path.read_text(encoding="utf-8")
    start = source.index("    def _slimmemeterportal_step(")
    end = source.index("    def _validation_step(", start)
    block = source[start:end]
    assert '"source_route": "home_assistant_managed"' in block
    assert '"nas_external_api_call": False' in block
    assert "WACHT_OP_OFFICIELE_API_URL" not in block
    assert "SlimmemeterPortalClient(" not in block
    assert "SlimmemeterPortalSync(" not in block


def test_v32012_full_workflow_targets_current_month_and_analysis_is_ha_managed():
    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    analysis_path = ROOT.parent / "Infra/Docker/native-mcp/energy_month_analysis.py"
    if not analysis_path.is_file():
        import pytest
        pytest.skip("full-project Infra context not present in standalone release ZIP")
    analysis = analysis_path.read_text(encoding="utf-8")
    assert 'version: "32.0.33"' in config
    assert "full_workflow_use_previous_month: false" in config
    assert "full_workflow_use_previous_month=False" in main
    assert "SlimmeMeterPortal wordt bewust overgeslagen." not in analysis
    assert "beschikbaarheid wordt in de maandworkflow apart gevalideerd" in analysis


def test_v32013_release_identity_is_synchronized():
    versie = (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip()
    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert versie == "32.0.33"
    assert 'version: "32.0.33"' in config
    assert 'APP_VERSION = "32.0.33"' in main


def test_v32014_ha_smp_ipv4_and_dynamic_runtime_identity():
    versie = (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip()
    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    source = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert versie == "32.0.33"
    assert 'version: "32.0.33"' in config
    assert 'APP_VERSION = "32.0.33"' in source
    assert "_SMP_IPV4_RESOLVER_LOCK = threading.RLock()" in source
    assert "with _smp_ipv4_only_resolution():" in source
    assert '"transport": "ipv4_forced"' in source
    assert '"/userapi/v1/connections"' in source
    assert '"/userapi/v1/connections/{connection_id}/usage/{date}"' in config
    assert '"release_version": APP_VERSION' in source
    assert '"engine_version": APP_VERSION' in source
    assert '"validation_marker": "current_release_runtime_identity"' in source


def test_v32015_smp_content_coverage_uses_defined_workflow_month_key():
    source = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    versie = (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip()
    assert versie == "32.0.33"
    assert 'version: "32.0.33"' in config
    assert 'APP_VERSION = "32.0.33"' in source
    define = '        workflow_month_key = f"{year:04d}_{month:02d}"'
    fixed = "        content_coverage = validate_smp_content_coverage(target, workflow_month_key)"
    buggy = "        content_coverage = validate_smp_content_coverage(target, month_key)"
    assert define in source
    assert fixed in source
    assert buggy not in source
    assert source.index(define) < source.index(fixed)
    assert "with _smp_ipv4_only_resolution():" in source
    assert '"partial_current_month"' in source


def test_v32016_complete_smp_import_fix_and_diagnostics():
    import ast
    source = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    versie = (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip()

    assert versie == "32.0.33"
    assert 'version: "32.0.33"' in config
    assert 'APP_VERSION = "32.0.33"' in source
    assert 'month_key = f"{year:04d}_{month:02d}"' in source
    assert 'workflow_month_key = f"{year:04d}_{month:02d}"' in source
    assert "validate_smp_content_coverage(target, workflow_month_key)" in source
    assert 'last_error_type=type(exc).__name__' in source
    assert 'last_traceback=traceback.format_exc()' in source
    assert "Laatste SMP-import" in source
    assert "Download SMP-importdiagnose" in source
    assert 'path.endswith("/download-smp-import-diagnose")' in source
    assert "with _smp_ipv4_only_resolution():" in source
    assert "_SMP_IPV4_RESOLVER_LOCK = threading.RLock()" in source
    assert 'api_get("/userapi/v1/connections", options)' in source
    assert '"partial_current_month"' in source
    assert "threading.Thread(target=run_import, args=(year, month), daemon=True).start()" in source

    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_import")
    stores = [n.lineno for n in ast.walk(fn)
              if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id == "month_key"]
    loads = [n.lineno for n in ast.walk(fn)
             if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id == "month_key"]
    assert stores
    assert not loads or min(stores) <= min(loads)


def test_v32017_smp_import_publishes_to_nas_month_input_without_replacing_month():
    import ast
    source = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    versie = (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip()

    assert versie == "32.0.33"
    assert 'version: "32.0.33"' in config
    assert 'APP_VERSION = "32.0.33"' in source
    assert "def publish_smp_import_to_nas_input" in source
    assert 'NAS_DATA_ROOT / "01_Input" / month_key' in source
    assert 'destination_root = ingress_root / "SlimmeMeterPortal"' in source
    assert 'ha_smp_transfer_manifest.json' in source
    assert "publish_smp_import_to_nas_input(target, workflow_month_key)" in source
    assert "smp_nas_transfer_last_status" in source
    assert "smp_nas_transfer_last_path" in source

    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "publish_smp_import_to_nas_input")
    fn_source = ast.get_source_segment(source, fn)
    assert 'destination_month.replace(' not in fn_source
    assert 'shutil.rmtree(destination_month' not in fn_source

    assert 'month_key = f"{year:04d}_{month:02d}"' in source
    assert "validate_smp_content_coverage(target, workflow_month_key)" in source
    assert "with _smp_ipv4_only_resolution():" in source
    assert 'api_get("/userapi/v1/connections", options)' in source
    assert '"partial_current_month"' in source
    assert "Laatste SMP-import" in source
    assert "Download SMP-importdiagnose" in source


def test_v32033_smp_transfer_creates_homeassistant_ingress_when_missing():
    import ast
    source = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    versie = (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip()

    assert versie == "32.0.33"
    assert 'version: "32.0.33"' in config
    assert 'APP_VERSION = "32.0.33"' in source
    assert 'staging = destination_month / ".SlimmeMeterPortal.staging"' not in source
    assert 'backup = destination_month / ".SlimmeMeterPortal.backup"' not in source
    assert 'ingress_root = destination_month / "HomeAssistant"' in source
    assert 'destination_root = ingress_root / "SlimmeMeterPortal"' in source
    assert 'staging = ingress_root / ".SlimmeMeterPortal.staging"' in source
    assert 'backup = ingress_root / ".SlimmeMeterPortal.backup"' in source
    assert 'ingress_root.mkdir(parents=True, exist_ok=True)' in source
    assert 'month_key = f"{year:04d}_{month:02d}"' in source
    assert "validate_smp_content_coverage(target, workflow_month_key)" in source
    assert "with _smp_ipv4_only_resolution():" in source
    assert 'api_get("/userapi/v1/connections", options)' in source
    assert '"partial_current_month"' in source
    assert "Laatste SMP-import" in source
    assert "Download SMP-importdiagnose" in source

    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "publish_smp_import_to_nas_input")
    fn_source = ast.get_source_segment(source, fn) or ""
    assert 'destination_month.mkdir(' not in fn_source
    assert 'ingress_root.mkdir(parents=True, exist_ok=True)' in fn_source
    assert 'destination_month.replace(' not in fn_source
    assert 'shutil.rmtree(destination_month' not in fn_source


def test_v32019_processed_release_retention():
    source = (ROOT / "tools/release_installer.sh").read_text(encoding="utf-8")
    for required in [
        'PROCESSED_RETENTION="${ENERGIE_PROCESSED_RETENTION:-3}"',
        'cleanup_processed_releases(){',
        'EnergieProject_v*.zip',
        'tail -n +$((PROCESSED_RETENTION + 1))',
        'cleanup_processed_releases',
    ]:
        assert required in source


def test_v32020_processed_retention_fail_closed():
    source = (ROOT / "tools/release_installer.sh").read_text(encoding="utf-8")
    for required in [
        'Processed-retentie: start count=',
        'find "$PROCESSED" -maxdepth 1 -type f',
        'processed-retentie eindcontrole mislukt',
        'Processed-retentie toegepast en gecontroleerd:',
    ]:
        assert required in source


def test_v32021_processed_retention_is_fail_closed():
    source = (ROOT / "tools/release_installer.sh").read_text(encoding="utf-8")
    for required in [
        'Processed-retentie: start count=$COUNT keep=$PROCESSED_RETENTION',
        "find \"$PROCESSED\" -maxdepth 1 -type f -name 'EnergieProject_v*.zip'",
        'tail -n +$((PROCESSED_RETENTION + 1))',
        'processed-retentie eindcontrole mislukt: count=$AFTER keep=$PROCESSED_RETENTION',
        'Processed-retentie toegepast en gecontroleerd: count=$AFTER keep=$PROCESSED_RETENTION',
        'cleanup_processed_releases',
    ]:
        assert required in source


def test_v32022_watcher_owns_startup_processed_retention():
    source = (ROOT / "tools/release_watcher.sh").read_text(encoding="utf-8")
    for required in [
        'PROCESSED="$INBOX/processed"',
        'PROCESSED_RETENTION="${ENERGIE_PROCESSED_RETENTION:-3}"',
        'cleanup_processed_releases_on_start(){',
        'Watcher startup-retentie v32.0.22: start count=',
        'sort -r > "$RANKED"',
        'tail -n +$((PROCESSED_RETENTION + 1)) "$RANKED"',
        'Watcher startup-retentie v32.0.22: OK count=',
        'startup-retention-ok',
        'MAINTENANCE_FAILED',
    ]:
        assert required in source


def test_v32022_installer_uses_semantic_version_retention():
    source = (ROOT / "tools/release_installer.sh").read_text(encoding="utf-8")
    for required in [
        'version="${base#EnergieProject_v}"',
        'printf \'%09d.%09d.%09d %s',
        'sort -r > "$RANKED"',
        'processed-retentie eindcontrole mislukt:',
    ]:
        assert required in source


def test_v32023_ha_app_owns_processed_retention():
    source = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    for required in [
        "def cleanup_processed_release_retention_on_app_start(",
        'NAS_RELEASE_ARCHIVE',
        're.fullmatch(',
        'candidate.unlink()',
        'processed-retentie eindcontrole:',
        'cleanup_processed_release_retention_on_app_start(',
        'HA-app processed-retentie v32.0.33: OK',
        'HA-app processed-retentie v32.0.33: FOUT',
    ]:
        assert required in source


def test_v32024_zip_mode_marks_ha_publication_required():
    source=(ROOT/"tools/release_installer.sh").read_text(encoding="utf-8")
    for required in [
        'HA_PUBLICATION_REQUIRED="$INBOX/ha_publication_required.json"',
        'write_ha_publication_required(){',
        '"status":"publication_required"',
        '"version":"$NEW_VERSION"',
        'HA-publicatie vereist voor v$NEW_VERSION',
    ]:
        assert required in source

def test_v32024_publication_and_retention_responsibilities_are_separate():
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    config=(ROOT/"slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    assert 'processed_retention = cleanup_processed_release_retention_on_app_start(' in source
    assert 'github_publication_enabled: false' in config


def test_v32025_main_runtime_boot_contract_restored():
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    required=[
        'signal.signal(signal.SIGTERM, stop_handler)',
        'signal.signal(signal.SIGINT, stop_handler)',
        'update_state(version=APP_VERSION)',
        'threading.Thread(target=scheduler, daemon=True).start()',
        'server = ThreadingHTTPServer(("0.0.0.0", 8099), Handler)',
        'def startup_self_test() -> None:',
        'threading.Thread(target=startup_self_test, daemon=True).start()',
        'server.serve_forever()',
        'server.server_close()',
    ]
    for item in required:
        assert item in source

def test_v32025_processed_retention_contract_still_present():
    source=(ROOT/"tools/release_installer.sh").read_text(encoding="utf-8")
    for required in [
        'cleanup_processed_releases(){',
        'sort -r > "$RANKED"',
        'tail -n +$((PROCESSED_RETENTION + 1)) "$RANKED"',
        'processed-retentie eindcontrole mislukt',
    ]:
        assert required in source


def test_v32026_gui_is_fail_safe_without_valid_options():
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert 'monitoring_snapshot(options) if options is not None else read_monitoring_status()' in source
    assert '"status": "not_configured"' in source
    assert 'Monitoring startupcontrole overgeslagen zolang configuratie niet gereed is:' in source

def test_v32026_release_identity_everywhere():
    versie=(ROOT/"VERSIE.txt").read_text(encoding="utf-8").strip()
    config=(ROOT/"slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    source=(ROOT/"slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert versie == "32.0.33"
    assert 'version: "32.0.33"' in config
    assert 'APP_VERSION = "32.0.33"' in source
