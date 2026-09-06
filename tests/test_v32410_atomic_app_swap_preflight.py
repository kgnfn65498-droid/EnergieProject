#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from tools.atomic_app_swap import (  # type: ignore[import-not-found]
    RecoveryRequired,
    SwapPaths,
    verify_release_artifact,
    verify_source_baseline,
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_source(root: Path, *, version: str = "32.4.9", pm_version: str = "2.0.0-rc6") -> None:
    app = root / "App"
    app.mkdir(parents=True, exist_ok=True)
    (app / "VERSIE.txt").write_text(version + "\n", encoding="utf-8")
    pm = app / "slimmemeterportal_import/rootfs/app/projectmanager_v2"
    pm.mkdir(parents=True, exist_ok=True)
    (pm / "VERSION.txt").write_text(pm_version + "\n", encoding="utf-8")


def snapshot(root: Path) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            result[rel] = ("dir", "")
        elif path.is_file():
            result[rel] = ("file", hashlib.sha256(path.read_bytes()).hexdigest())
    return result


class AtomicSwapArtifactBaselinePreflightTests(unittest.TestCase):
    def test_wrong_artifact_sha_causes_zero_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "release.zip"
            artifact.write_bytes(b"candidate-bytes")
            before = snapshot(root)

            with self.assertRaisesRegex(ValueError, "artifact sha256"):
                verify_release_artifact(artifact, "0" * 64)

            self.assertEqual(snapshot(root), before)

    def test_matching_artifact_sha_is_returned_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "release.zip"
            payload = b"candidate-bytes"
            artifact.write_bytes(payload)
            expected = sha256_bytes(payload)
            before = snapshot(root)

            actual = verify_release_artifact(artifact, expected)

            self.assertEqual(actual, expected)
            self.assertEqual(snapshot(root), before)

    def test_wrong_source_version_causes_zero_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            write_source(root, version="32.4.8")
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            before = snapshot(root)

            with self.assertRaisesRegex(RecoveryRequired, "source version"):
                verify_source_baseline(paths, expected_pm_version="2.0.0-rc6")

            self.assertEqual(snapshot(root), before)

    def test_wrong_source_pm_version_causes_zero_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            write_source(root, pm_version="2.0.0-rc5")
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            before = snapshot(root)

            with self.assertRaisesRegex(RecoveryRequired, "source PM version"):
                verify_source_baseline(paths, expected_pm_version="2.0.0-rc6")

            self.assertEqual(snapshot(root), before)

    def test_unexpected_existing_rollback_fails_closed_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            write_source(root)
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            paths.rollback.mkdir()
            before = snapshot(root)

            with self.assertRaisesRegex(RecoveryRequired, "rollback"):
                verify_source_baseline(paths, expected_pm_version="2.0.0-rc6")

            self.assertEqual(snapshot(root), before)

    def test_unexpected_existing_candidate_fails_closed_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            write_source(root)
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            paths.candidate.mkdir()
            before = snapshot(root)

            with self.assertRaisesRegex(RecoveryRequired, "candidate"):
                verify_source_baseline(paths, expected_pm_version="2.0.0-rc6")

            self.assertEqual(snapshot(root), before)

    def test_valid_source_baseline_reports_exact_identity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            write_source(root)
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            before = snapshot(root)

            result = verify_source_baseline(paths, expected_pm_version="2.0.0-rc6")

            self.assertEqual(result["source_version"], "32.4.9")
            self.assertEqual(result["source_pm_version"], "2.0.0-rc6")
            self.assertEqual(snapshot(root), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
