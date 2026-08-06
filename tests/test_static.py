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
    assert cfg_version == app_version == "3.9.1"

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
