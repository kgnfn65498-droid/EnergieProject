from __future__ import annotations

import pathlib
import shutil
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "slimmemeterportal_import/rootfs/app"
sys.path.insert(0, str(APP_ROOT))

import main


def _write_tree(root: pathlib.Path, version: str, manifest_text: str, payload: str = "same") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "VERSIE.txt").write_text(version + "\n", encoding="utf-8")
    (root / "payload.txt").write_text(payload + "\n", encoding="utf-8")
    (root / "MANIFEST.sha256").write_text(manifest_text, encoding="utf-8")
    (root / "SHA256SUMS.json").write_text('{"generated": true}\n', encoding="utf-8")


def _contract(previous_version="32.3.16", target_version="32.3.17"):
    return {
        "expected_previous_version": previous_version,
        "expected_previous_manifest_sha256": "previous-manifest-sha",
        "version": target_version,
        "target_manifest_sha256": "target-manifest-sha",
    }


def test_prepublished_target_source_match_allows_release_metadata_sync(tmp_path, monkeypatch):
    remote = tmp_path / "remote"
    release = tmp_path / "release"
    _write_tree(remote, "32.3.17", "remote metadata differs\n")
    _write_tree(release, "32.3.17", "release metadata differs\n")

    monkeypatch.setattr(main, "_manifest_file_sha256", lambda root: {
        remote: "remote-manifest-sha",
        release: "target-manifest-sha",
    }[pathlib.Path(root)])

    ok, state, message = main._classify_github_remote_baseline(_contract(), remote, release)

    assert ok is True
    assert state == "target_source_match"
    assert "reeds" in message.lower() or "target" in message.lower()


def test_prepublished_target_with_real_source_difference_stays_fail_closed(tmp_path, monkeypatch):
    remote = tmp_path / "remote"
    release = tmp_path / "release"
    _write_tree(remote, "32.3.17", "remote metadata differs\n", payload="REMOTE DIFFERENT")
    _write_tree(release, "32.3.17", "release metadata differs\n", payload="RELEASE DIFFERENT")

    monkeypatch.setattr(main, "_manifest_file_sha256", lambda root: {
        remote: "remote-manifest-sha",
        release: "target-manifest-sha",
    }[pathlib.Path(root)])

    ok, state, message = main._classify_github_remote_baseline(_contract(), remote, release)

    assert ok is False
    assert state == "mismatch"
    assert "bron" in message.lower() or "source" in message.lower()


def test_previous_and_exact_target_states_remain_strict(tmp_path, monkeypatch):
    previous = tmp_path / "previous"
    target = tmp_path / "target"
    release = tmp_path / "release"
    _write_tree(previous, "32.3.16", "previous\n")
    _write_tree(target, "32.3.17", "target\n")
    _write_tree(release, "32.3.17", "target\n")

    values = {
        previous: "previous-manifest-sha",
        target: "target-manifest-sha",
        release: "target-manifest-sha",
    }
    monkeypatch.setattr(main, "_manifest_file_sha256", lambda root: values[pathlib.Path(root)])
    monkeypatch.setattr(main, "_verify_release_manifest", lambda root: (True, "ok"))

    assert main._classify_github_remote_baseline(_contract(), previous, release)[:2] == (True, "previous")
    assert main._classify_github_remote_baseline(_contract(), target, release)[:2] == (True, "target_exact")


def test_exact_target_manifest_hash_with_tampered_remote_files_stays_fail_closed(tmp_path, monkeypatch):
    remote = tmp_path / "remote"
    release = tmp_path / "release"
    _write_tree(remote, "32.3.17", "same manifest bytes\n", payload="tampered")
    _write_tree(release, "32.3.17", "same manifest bytes\n", payload="validated")
    monkeypatch.setattr(main, "_manifest_file_sha256", lambda root: "target-manifest-sha")
    monkeypatch.setattr(main, "_verify_release_manifest", lambda root: (False, "Manifesthash wijkt af: payload.txt"))

    ok, state, message = main._classify_github_remote_baseline(_contract(), remote, release)

    assert ok is False
    assert state == "mismatch"
    assert "remote bron" in message.lower()


def test_exact_target_publication_clears_contract_without_push(tmp_path, monkeypatch):
    contract_marker = tmp_path / "ha_publication_required.json"
    contract_marker.write_text("{}\n", encoding="utf-8")
    worktree = tmp_path / "worktree"
    release = tmp_path / "release"
    _write_tree(worktree, "32.3.17", "target\n")
    _write_tree(release, "32.3.17", "target\n")

    contract = {
        **_contract(),
        "processed_path": str(tmp_path / "processed.zip"),
    }
    monkeypatch.setattr(main, "HA_PUBLICATION_REQUIRED", contract_marker)
    monkeypatch.setattr(main, "GITHUB_WORKTREE", worktree)
    monkeypatch.setattr(main, "github_publication_status", lambda options=None: {
        "enabled": True,
        "repository": "git@github.com:kgnfn65498-droid/EnergieProject.git",
        "branch": "main",
        "key_ready": True,
        "message": "ready",
    })
    monkeypatch.setattr(main, "_load_github_publication_contract", lambda options=None: (True, contract, "ok"))
    monkeypatch.setattr(main, "_prepare_github_worktree", lambda repo, branch, env: (True, "ok"))
    monkeypatch.setattr(main, "_prepare_validated_publication_source", lambda c: (True, release, "ok"))
    monkeypatch.setattr(main, "_github_git_env", lambda: {})
    monkeypatch.setattr(main, "_classify_github_remote_baseline", lambda c, w, r: (True, "target_exact", "already target"))
    monkeypatch.setattr(main, "_sync_project_to_github_worktree", lambda *a, **k: pytest.fail("sync must not run"))
    monkeypatch.setattr(main, "_run_cmd", lambda *a, **k: pytest.fail("git command must not run after target_exact"))

    result = main.publish_github_release({
        "github_publication_enabled": True,
        "github_repository_ssh": "git@github.com:kgnfn65498-droid/EnergieProject.git",
        "github_branch": "main",
    })

    assert result["published"] is True
    assert result["already_published"] is True
    assert result["publication_contract_removed"] is True
    assert not contract_marker.exists()
