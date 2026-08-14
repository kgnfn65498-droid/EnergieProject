#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import" / "rootfs" / "app" / "main.py"
CONFIG = ROOT / "slimmemeterportal_import" / "config.yaml"
VERSIE = ROOT / "VERSIE.txt"
STATIC = ROOT / "tests" / "test_static.py"
CHANGELOG = ROOT / "CHANGELOG.md"
EXPECTED_BRANCH = "feature/v32.0.29-crash-recovery-export"

CHANGELOG_ENTRY = """## v32.0.29 — Crash Recovery browser/iCloud export

- Complete Crash Recovery levert na create/deep verify en veilige `RestoreStaging` één herstelvriendelijke browser-ZIP met exact top-level `EnergieProject/`.
- De export bevat de volledige actuele projectinhoud, inclusief normale maandbackups, manifests, logs en herstelhandleidingen. Alleen `Energie_Complete_Backup_*.zip`, `FULL_RECOVERY*.tar.gz` en `.DS_Store` worden niet opnieuw ingepakt.
- Na een volledig succesvolle browserdownload worden uitsluitend run-specifieke tijdelijke Crash-Recovery-artefacten op de NAS opgeruimd; een afgebroken download blijft retrybaar en verwijdert niets.
- Geen `finalize_month`, geen live restore en geen wijziging van de normale NAS-backupretentie.

"""


def replace_exact(text: str, old: str, new: str, expected: int, label: str) -> str:
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: verwacht {expected}x {old!r}, gevonden {count}")
    return text.replace(old, new)


def main() -> None:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        branch = os.environ.get("GITHUB_REF_NAME", "")
        if branch != EXPECTED_BRANCH:
            raise RuntimeError(f"weigering buiten featurebranch: {branch!r}")

    main_text = MAIN.read_text(encoding="utf-8")
    config_text = CONFIG.read_text(encoding="utf-8")
    static_text = STATIC.read_text(encoding="utf-8")
    changelog_text = CHANGELOG.read_text(encoding="utf-8")

    already_done = (
        VERSIE.read_text(encoding="utf-8").strip() == "32.0.29"
        and 'APP_VERSION = "32.0.29"' in main_text
        and 'version: "32.0.29"' in config_text
        and '"32.0.28"' not in static_text
        and changelog_text.startswith(CHANGELOG_ENTRY)
    )
    if already_done:
        print("V32_0_29_IDENTITY_ALREADY_PRESENT")
        return

    main_text = replace_exact(
        main_text,
        'APP_VERSION = "32.0.28"',
        'APP_VERSION = "32.0.29"',
        1,
        "APP_VERSION",
    )
    main_text = replace_exact(
        main_text,
        "HA-app processed-retentie v32.0.28: OK",
        "HA-app processed-retentie v32.0.29: OK",
        1,
        "processed retention OK label",
    )
    main_text = replace_exact(
        main_text,
        "HA-app processed-retentie v32.0.28: FOUT",
        "HA-app processed-retentie v32.0.29: FOUT",
        1,
        "processed retention FOUT label",
    )
    if 'PRODUCTION_CORE_REVISION = "9.4-core1"' not in main_text:
        raise RuntimeError("PRODUCTION_CORE_REVISION 9.4-core1 ontbreekt; releasebump geweigerd")

    config_text = replace_exact(
        config_text,
        'version: "32.0.28"',
        'version: "32.0.29"',
        1,
        "config version",
    )

    old_count = static_text.count("32.0.28")
    if old_count < 1:
        raise RuntimeError("test_static.py bevat geen 32.0.28 releaseverwachtingen")
    static_text = static_text.replace("32.0.28", "32.0.29")

    if changelog_text.startswith("## v32.0.29 — Crash Recovery browser/iCloud export"):
        pass
    else:
        changelog_text = CHANGELOG_ENTRY + changelog_text

    MAIN.write_text(main_text, encoding="utf-8")
    CONFIG.write_text(config_text, encoding="utf-8")
    VERSIE.write_text("32.0.29\n", encoding="utf-8")
    STATIC.write_text(static_text, encoding="utf-8")
    CHANGELOG.write_text(changelog_text, encoding="utf-8")

    print(f"V32_0_29_IDENTITY_PATCH_OK static_replacements={old_count}")


if __name__ == "__main__":
    main()
