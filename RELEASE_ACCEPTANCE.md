# Release Acceptance — 32.4.64

Release Acceptance validates the production release chain itself. It is distinct from Platform Qualification tests that depend on host capabilities such as child-process preexec, AF_UNIX sockets, uid/gid switching, or legacy local-runtime import topology.

Required V64 release invariants:
- one ReleaseController lifecycle owner;
- PUBLISHING before INSTALLING;
- predecessor publishes successor to exact GitHub target;
- predecessor Supervisor action is only `/store/reload`;
- no automatic `/store/addons/<slug>/update`, install, rebuild, or second actuator path;
- exact GitHub + predecessor HA runtime => durable `WAITING_MANUAL_HA_UPDATE`;
- Processing remains transactional owner during that wait;
- exact GitHub + exact HA target runtime => contract settlement, archive to Processed, COMPLETE;
- settlement/archive is crash-safe and idempotent;
- synthetic N+1 regression proves 32.4.64 already behaves correctly as predecessor for 32.4.65.

Source acceptance evidence before canonical build:
- focused V56/V58/V60/V61/V62/V63/V64 chain set: 64/64 GREEN;
- modern V56–V64 release group: 200/200 GREEN;
- broader stable release-compatible groups: 1796 passed, 2 skipped, no failures.

The exact fresh-extract run must repeat the release-chain acceptance set before final artifact approval.
