#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import" / "rootfs" / "app" / "main.py"
EXPECTED_BRANCH = "feature/v32.0.29-crash-recovery-export"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: verwacht exact 1 anchor, gevonden {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        branch = os.environ.get("GITHUB_REF_NAME", "")
        if branch != EXPECTED_BRANCH:
            raise RuntimeError(f"weigering buiten featurebranch: {branch!r}")

    text = MAIN.read_text(encoding="utf-8")
    if 'id="complete-recovery-export-count"' in text:
        print("V32_0_29_GUI_PATCH_ALREADY_PRESENT")
        return
    if "def _stream_complete_recovery_download(" not in text:
        raise RuntimeError("downloadlaag ontbreekt; GUI-patch geweigerd")

    text = replace_once(
        text,
        '<div class="metric"><small>Deep verify</small><strong id="complete-recovery-count">-</strong></div>\n'
        '<div class="metric"><small>SHA-256</small><strong id="complete-recovery-sha">-</strong></div>',
        '<div class="metric"><small>Deep verify</small><strong id="complete-recovery-count">-</strong></div>\n'
        '<div class="metric"><small>Export bestanden</small><strong id="complete-recovery-export-count">-</strong></div>\n'
        '<div class="metric"><small>SHA-256</small><strong id="complete-recovery-sha">-</strong></div>',
        "export count metric",
    )

    text = replace_once(
        text,
        "  const count=document.getElementById('complete-recovery-count');\n"
        "  const sha=document.getElementById('complete-recovery-sha');\n",
        "  const count=document.getElementById('complete-recovery-count');\n"
        "  const exportCount=document.getElementById('complete-recovery-export-count');\n"
        "  const sha=document.getElementById('complete-recovery-sha');\n",
        "export count js const",
    )

    text = replace_once(
        text,
        "  if(name) name.textContent=String(result.backup_name||'-');\n",
        "  if(name) name.textContent=String(result.export_name||result.backup_name||'-');\n",
        "export name render",
    )

    text = replace_once(
        text,
        "  if(count){{\n"
        "    const verified=Number(result.verified_files||0);\n"
        "    const total=Number(result.manifest_file_count||0);\n"
        "    count.textContent=(verified&&total)?`${{verified}} / ${{total}}`:'-';\n"
        "  }}\n"
        "  if(sha) sha.textContent=String(result.sha256||'-');\n",
        "  if(count){{\n"
        "    const verified=Number(result.verified_files||0);\n"
        "    const total=Number(result.manifest_file_count||0);\n"
        "    count.textContent=(verified&&total)?`${{verified}} / ${{total}}`:'-';\n"
        "  }}\n"
        "  if(exportCount) exportCount.textContent=String(result.export_file_count||'-');\n"
        "  if(sha) sha.textContent=String(result.export_sha256||result.backup_sha256||result.sha256||'-');\n",
        "export identity render",
    )

    text = replace_once(
        text,
        "  if(detail){{\n"
        "    if(result.error) detail.textContent=String(result.error);\n"
        "    else if(result.restore_test_status==='staged') detail.textContent='Hersteltest geslaagd in geïsoleerde RestoreStaging.';\n"
        "    else if(result.status==='verified') detail.textContent='Complete Crash Recovery is deep geverifieerd. Augustus/lopende maand is niet afgesloten.';\n"
        "  }}\n",
        "  if(detail){{\n"
        "    if(result.error) detail.textContent=String(result.error);\n"
        "    else if(result.status==='retry_available'||result.download_status==='retry_available') detail.textContent='De download is afgebroken; niets is opgeruimd. Je kunt opnieuw downloaden.';\n"
        "    else if(result.status==='ready_for_download') detail.textContent='Crash Recovery is volledig geverifieerd en RestoreStaging is geslaagd. Download de ZIP en bewaar hem zelf in iCloud.';\n"
        "    else if(result.status==='downloaded'&&result.cleanup_status==='ok') detail.textContent='Download afgerond; tijdelijke Crash-Recovery-bestanden op de NAS zijn opgeruimd.';\n"
        "    else if(result.status==='downloaded') detail.textContent='Download afgerond; tijdelijke cleanup heeft aandacht nodig.';\n"
        "    else if(result.restore_test_status==='staged') detail.textContent='Hersteltest geslaagd in geïsoleerde RestoreStaging.';\n"
        "    else if(result.status==='verified') detail.textContent='Complete Crash Recovery is deep geverifieerd. Augustus/lopende maand is niet afgesloten.';\n"
        "  }}\n",
        "download detail render",
    )

    MAIN.write_text(text, encoding="utf-8")
    print("V32_0_29_GUI_PATCH_OK")


if __name__ == "__main__":
    main()
