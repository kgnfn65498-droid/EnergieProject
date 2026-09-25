# Release Acceptance — 32.5.9

Status vóór live installatie: RELEASE CANDIDATE, niet live bewezen.

Verplicht GREEN vóór aanbieding:
1. exact-ZIP integriteit en manifests;
2. 32.5.x regressies;
3. ClearUp Type1 real commandprocessor -> sideband -> privileged delete/readback;
4. ClearUp Type2 002..012 prepare -> migrate -> activate -> validate -> finalize -> restore;
5. stale predecessor request -> archive -> current exact request -> no incoming starvation;
6. exact-current-fence conflict blijft fail-closed;
7. manual Native-MCP reload blijft beschermd door expliciete Peter approval;
8. fresh-extract test en Python compile.

Na installatie blijft live runtime fingerprint/readback vereist voordat destructieve ClearUp wordt uitgevoerd.
