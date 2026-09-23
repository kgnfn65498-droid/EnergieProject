# Platform Qualification — 32.4.64

Platform Qualification is intentionally separate from Release Acceptance. No test is deleted, xfailed, or weakened to obtain release GREEN.

Known harness/host limitations observed in this Chat runtime:
- `tests/test_offline_test_guard.py::test_child_python_installs_guard_before_application_imports`: child interpreter sees the platform `/opt/sitecustomize` ordering and reports the repository guard as not preinstalled;
- `tests/test_v32419_watcher_freshness.py`: legacy shell/subprocess test can hang under this restricted executor;
- V63 full-suite evidence previously reached 2013 passed, 2 skipped with 3 host-capability failures in `tests/test_v32453_final_closure` involving preexec, AF_UNIX socket creation, and uid/gid identity operations;
- some older platform/orchestration files are order-sensitive when executed in isolation because they assume legacy import-path initialization.

These limitations are not converted into Release Acceptance failures unless they touch the active V64 release-chain code. The active V64 chain is tested independently with isolated filesystem state and mocked Supervisor transport.
