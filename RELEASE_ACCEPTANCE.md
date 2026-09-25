# Release Acceptance — 32.5.13

Status vóór live installatie: RELEASE CANDIDATE, niet live bewezen.

Verplicht GREEN vóór aanbieding:
1. exact-ZIP integriteit en manifests;
2. 32.5.x regressies;
3. ClearUp Type1 real commandprocessor -> sideband -> privileged delete/readback;
4. ClearUp Type2 002..012 prepare -> migrate -> activate -> validate -> finalize -> restore;
5. stale predecessor request -> archive -> current exact request -> no incoming starvation;
6. exact-current-fence conflict blijft fail-closed;
7. manual Native-MCP reload blijft beschermd door expliciete Peter approval;
8. fresh-extract test en Python compile;
9. existing `projectmanager_status` tool remains the transport surface; no new MCP tool name;
10. signed download URL is emitted only under the exact external-recovery gate and binds ClearUp id + expiry + current ZIP SHA-256;
11. invalid/expired signature, unsupported ID and changed ZIP identity fail closed;
12. download route performs no filesystem write/delete/migrate/finalize.

Na installatie blijft live runtime fingerprint/readback vereist voordat destructieve ClearUp wordt uitgevoerd.
