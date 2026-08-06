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
    assert cfg_version == app_version == "5.0.0"

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
    assert 'version: "5.0.0"' in config
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
    assert 'validation.get("status") != "ok"' in source
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
    assert "onvolledige doelmap is verwijderd" in source
    assert "ZIP-verificatie mislukt; overdracht is teruggedraaid" in source

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
