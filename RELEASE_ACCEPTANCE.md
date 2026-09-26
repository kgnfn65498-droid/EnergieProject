# Release Acceptance — 32.5.22

Status: READY_FOR_USER_INCOMING

## Scope
1. Repareer uitsluitend de live ClearUp_007 writer-binding die op 32.5.21 nog naar retired `Inbox/control_plane` schrijft.
2. Bewijs de live containerbinding aan command + mounts; een correcte fingerprint/health alleen is niet genoeg na Type-2 path activation.
3. Bij legacy binding: één bounded recreate naar de canonieke ControlPlane/ReleaseController/NativeMCP mounts, met exacte readback en rollback naar de vorige container bij mislukking.
4. Laat de qnap control-plane bootstrap zijn security-migratiemarkering na recreate in de canonieke ReleaseController schrijven.
5. Behoud alle bestaande Type-2 recovery-, validation-, external-copy- en finalize/delete-gates.

## Live bewijs
- 32.5.21 is COMPLETE 9/9; PM `2.0.0-rc54`; canonieke HA-runtime is 32.5.21.
- ClearUp_005 migrate + validate: GREEN.
- ClearUp_006 validate: GREEN.
- ClearUp_007 validate: RED met `old_source_still_mutating:Inbox/control_plane` en `runtime_writer_proof_missing:Inbox/control_plane`.
- Live legacy `Inbox/control_plane/runtime.json` bleef schrijven terwijl canonieke `Data/.../ControlPlane/Runtime/runtime.json` stil stond; beide droegen dezelfde codefingerprint. Daarmee is de fout container-binding, niet codefingerprint.
- Bestaande `stale_but_exact` bootstraplogica accepteerde health+fingerprint zonder de actieve mount/commandbinding te bewijzen.
- Geen finalize/delete uitgevoerd.

## Acceptance-eisen
- Nieuwe 32.5.22 regressies voor active-mapping binding detectie, één bounded recreate en canonieke security-marker: GREEN.
- Historische releasecontroller/control-plane regressies blijven GREEN.
- Type-2/v32.5 suite en static suite GREEN.
- Fresh-extract, compileall, manifest/CRC/hash/safe-entry en exact atomic 32.5.21→32.5.22 GREEN.
- Na live installatie: ClearUp_007 revalidate moet GREEN; daarna 002–012 allemaal GREEN.
- Voor finalize/delete wordt de ACTUELE post-migrate recoveryset opnieuw rechtstreeks in chat geleverd en door Peter bevestigd.

## Finale buildacceptatie
- Nieuwe/impact regressies: 52/52 GREEN.
- Volledige 32.5-suite: 134/134 GREEN, 1 bekende duplicate-name warning uit de corrupte-ZIP regressietest.
- Static: 600/600 GREEN, 2 skipped.
- Fresh-extract: 45/45 targeted GREEN; static 600/600 GREEN, 2 skipped; compileall GREEN.
- Exact geïsoleerde atomic 32.5.21→32.5.22: LIVE_ACCEPTANCE → ACCEPTED.
- Release artifact builder: manifest/CRC/payload hashes/safe entries GREEN.
