from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCHER = ROOT/'tests/fixtures/pre57/release_watcher.sh'
RECOVERY = ROOT/'tools/release_ingress_recovery.py'
RELEASE_ZIP = ROOT/'tools/release_zip.py'


def _valid_zip(path: Path) -> bytes:
    temp = path.parent/'full.zip'
    with zipfile.ZipFile(temp, 'w') as zf:
        zf.writestr('VERSIE.txt', '32.4.55\n')
        zf.writestr('README.md', 'ok\n')
    data = temp.read_bytes(); temp.unlink()
    return data


def _make_root(tmp_path: Path) -> tuple[Path, dict[str,str]]:
    root = tmp_path/'energy'
    tools = root/'App/tools'; tools.mkdir(parents=True)
    for rel in ('Inbox/incoming','Inbox/processing','Inbox/processed','Inbox/failed','Inbox/logs'):
        (root/rel).mkdir(parents=True, exist_ok=True)
    (tools/'release_ingress_recovery.py').write_bytes(RECOVERY.read_bytes())
    (tools/'release_zip.py').write_bytes(RELEASE_ZIP.read_bytes())
    (tools/'operating_mode_gate.py').write_text(
        'import argparse\n'
        'p=argparse.ArgumentParser(); p.add_argument("--root"); p.add_argument("--capability"); a=p.parse_args()\n'
        'raise SystemExit(0 if a.capability == "release_ingress" else 3)\n', encoding='utf-8')
    (tools/'release_transition_bootstrap.py').write_text('import sys\nraise SystemExit(0)\n', encoding='utf-8')
    (tools/'release_preflight.py').write_text(
        'import argparse, pathlib\n'
        'p=argparse.ArgumentParser(); p.add_argument("--root"); p.add_argument("--candidate"); a=p.parse_args()\n'
        'raise SystemExit(0 if pathlib.Path(a.candidate).is_file() else 3)\n', encoding='utf-8')
    # After a successful install the real watcher re-execs the newly installed
    # watcher. A tiny clean exit keeps this isolated practical harness bounded.
    (tools/'release_watcher.sh').write_text('#!/bin/sh\nexit 0\n', encoding='utf-8')
    (tools/'release_watcher.sh').chmod(0o755)
    (tools/'release_installer.sh').write_text(
        '#!/bin/sh\nset -eu\n'
        'ROOT="$ENERGIE_ROOT"\n'
        'mkdir -p "$ROOT/Inbox/processing" "$ROOT/Inbox/processed" "$ROOT/Inbox/logs"\n'
        'set -- "$ROOT/Inbox/incoming"/*.zip\n'
        '[ -e "$1" ] || exit 0\n'
        '[ "$#" -eq 1 ] || exit 7\n'
        'name=$(basename "$1")\n'
        'mv "$1" "$ROOT/Inbox/processing/$name"\n'
        'printf "claim %s\\n" "$name" >> "$ROOT/Inbox/logs/practical-installer-count"\n'
        'mv "$ROOT/Inbox/processing/$name" "$ROOT/Inbox/processed/$name"\n', encoding='utf-8')
    (tools/'release_installer.sh').chmod(0o755)
    fast_bin = root/'test-bin'; fast_bin.mkdir()
    pywrap = fast_bin/'python3'
    pywrap.write_text(
        '#!/bin/sh\n'
        'case "$1" in\n'
        '  */operating_mode_gate.py)\n'
        '    cap=; prev=\n'
        '    for arg in "$@"; do [ "$prev" = "--capability" ] && cap="$arg"; prev="$arg"; done\n'
        '    [ "$cap" = "release_ingress" ] && exit 0 || exit 3 ;;\n'
        '  */release_transition_bootstrap.py) exit 0 ;;\n'
        '  */release_preflight.py)\n'
        '    candidate=; prev=\n'
        '    for arg in "$@"; do [ "$prev" = "--candidate" ] && candidate="$arg"; prev="$arg"; done\n'
        '    [ -n "$candidate" ] && [ -f "$candidate" ] && exit 0 || exit 3 ;;\n'
        'esac\n'
        'exec "$REAL_PYTHON" "$@"\n', encoding='utf-8')
    pywrap.chmod(0o755)
    env = os.environ.copy()
    env.update({
        'ENERGIE_ROOT': str(root),
        'ENERGIE_WATCHER_REEXEC': '1',
        'ENERGIE_WATCH_INTERVAL': '0.1',
        'REAL_PYTHON': sys.executable,
        'PATH': str(fast_bin) + os.pathsep + env.get('PATH', ''),
        'ENERGIE_ZIP_STABLE_POLLS': '3',
        'ENERGIE_INGRESS_RECOVERY_STALE_SECONDS': '30',
        'ENERGIE_PROCESSED_RETENTION': '10',
    })
    return root, env


def _start(root: Path, env: dict[str,str]) -> subprocess.Popen:
    return subprocess.Popen(
        ['sh', str(WATCHER), 'run'], env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True,
    )


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try: proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill(); proc.wait(timeout=3)


def _claims(root: Path) -> list[str]:
    path=root/'Inbox/logs/practical-installer-count'
    return path.read_text(encoding='utf-8').splitlines() if path.is_file() else []


def _wait_for(predicate, timeout=10.0):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate(): return True
        time.sleep(0.1)
    return bool(predicate())


def test_slow_partial_copy_is_never_claimed_and_full_stable_zip_is_claimed_once(tmp_path: Path):
    root,env=_make_root(tmp_path)
    data=_valid_zip(tmp_path/'unused')
    target=root/'Inbox/incoming/EnergieProject_v32.4.55.zip'
    proc=_start(root,env)
    try:
        cut1=len(data)//3; cut2=2*len(data)//3
        target.write_bytes(data[:cut1]); time.sleep(1.2)
        assert _claims(root)==[]
        with target.open('ab') as h: h.write(data[cut1:cut2])
        time.sleep(1.2); assert _claims(root)==[]
        with target.open('ab') as h: h.write(data[cut2:])
        assert _wait_for(lambda: len(_claims(root))==1, timeout=6)
        assert len(_claims(root))==1
        assert (root/'Inbox/processed'/target.name).is_file()
        assert not list((root/'Inbox/failed').rglob('*.zip'))
    finally: _stop(proc)


def test_watcher_restart_before_claim_never_double_claims(tmp_path: Path):
    root,env=_make_root(tmp_path)
    target=root/'Inbox/incoming/EnergieProject_v32.4.55.zip'; target.write_bytes(_valid_zip(tmp_path/'unused'))
    first=_start(root,env)
    time.sleep(1.3)
    assert _claims(root)==[]
    _stop(first)
    second=_start(root,env)
    try:
        assert _wait_for(lambda: len(_claims(root))==1, timeout=7)
        time.sleep(1.2)
        assert len(_claims(root))==1
    finally: _stop(second)


def test_stale_watcher_lock_pid_and_heartbeat_recover_without_duplicate_claim(tmp_path: Path):
    root,env=_make_root(tmp_path)
    lock=root/'Inbox/.watcher.lock'; lock.mkdir()
    (root/'Inbox/.watcher.pid').write_text('999999\n', encoding='utf-8')
    hb=root/'Inbox/.watcher.heartbeat'; hb.write_text('1\n', encoding='utf-8')
    old=time.time()-120; os.utime(hb,(old,old))
    target=root/'Inbox/incoming/EnergieProject_v32.4.55.zip'; target.write_bytes(_valid_zip(tmp_path/'unused'))
    proc=_start(root,env)
    try:
        assert _wait_for(lambda: len(_claims(root))==1, timeout=7)
        assert len(_claims(root))==1
    finally: _stop(proc)


def test_n_plus_one_waits_during_live_acceptance_then_processes_once_after_acceptance(tmp_path: Path):
    root,env=_make_root(tmp_path)
    journal=root/'Inbox/atomic_app_swap_state.json'
    journal.write_text(json.dumps({'state':'LIVE_ACCEPTANCE','to_version':'32.4.54'}), encoding='utf-8')
    target=root/'Inbox/incoming/EnergieProject_v32.4.55.zip'; target.write_bytes(_valid_zip(tmp_path/'unused'))
    proc=_start(root,env)
    try:
        time.sleep(4.2)
        assert _claims(root)==[]
        assert target.is_file()
        journal.write_text(json.dumps({'state':'ACCEPTED','to_version':'32.4.54'}), encoding='utf-8')
        assert _wait_for(lambda: len(_claims(root))==1, timeout=6)
        time.sleep(1.0)
        assert len(_claims(root))==1
    finally: _stop(proc)


def test_bounded_runner_returns_promptly_when_command_finishes_early():
    text = WATCHER.read_text(encoding="utf-8")
    fn = "run_bounded(){" + text.split("run_bounded(){", 1)[1].split("\n}", 1)[0] + "\n}"
    started = time.monotonic()
    proc = subprocess.run(
        ["sh", "-c", fn + "\nBOUNDED_TERM_GRACE_SECONDS=0\nrun_bounded 2 sleep 0.05"],
        text=True, capture_output=True, check=False, timeout=4,
    )
    elapsed = time.monotonic() - started
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert elapsed < 0.8, (elapsed, proc.stdout, proc.stderr)


def test_partial_copy_may_pause_beyond_stable_polls_and_resume_without_quarantine(tmp_path: Path):
    root,env=_make_root(tmp_path)
    env['ENERGIE_ZIP_STABLE_POLLS'] = '1'
    data=_valid_zip(tmp_path/'unused')
    target=root/'Inbox/incoming/EnergieProject_v32.4.55.zip'
    proc=_start(root,env)
    try:
        cut=max(1, len(data)//2)
        target.write_bytes(data[:cut])
        # Longer than the three 0.1s watcher stability polls, but far younger
        # than the configured 30s stale/corruption boundary.
        time.sleep(4.0)
        assert target.is_file(), 'temporarily stalled partial copy must stay in Incoming'
        assert _claims(root)==[]
        assert not list((root/'Inbox/failed').rglob('*.zip'))
        with target.open('ab') as h:
            h.write(data[cut:])
        assert _wait_for(lambda: len(_claims(root))==1, timeout=7)
        assert len(_claims(root))==1
        assert (root/'Inbox/processed'/target.name).is_file()
        assert not list((root/'Inbox/failed').rglob('*.zip'))
    finally:
        _stop(proc)
