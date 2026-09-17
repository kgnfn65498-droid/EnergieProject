# Changelog

## 32.4.55 — autonomous release ingress recovery

- Incoming herstelt identieke dubbele release-ZIPs deterministisch en blokkeert verschillende kandidaten fail-closed.
- Orphan Processing wordt alleen na bewezen stale/absent installer-eigendom veilig teruggezet naar Incoming.
- Installer-lock gebruikt owner + heartbeat; stale recovery verwijdert uitsluitend de strikt bekende lock-inhoud.
- Stabiele corrupte ZIPs worden bounded naar `Inbox/failed/corrupt` gequarantaineerd in plaats van Incoming permanent te blokkeren.
- Generation-fenced release-transition recovery en coherente FINAL Projectmanager-provenance blijven behouden.
- RuntimeV2 cross-runtime state normaliseert directories naar 0777 en JSON-state naar 0666; symlinktargets falen gesloten.
- Document-sync behoudt bestaande bestandsmodus zodat KB/status-documenten niet terugvallen naar 0600.
- Incoming recovery gebruikt lstat-first voor installer-lock, owner en heartbeat; dangling symlinks blijven BLOCKED zonder requeue.
- NAS Container CR Docker image-export gebruikt een 600s read-timeout voor de bewezen 500MB+ export.
- CLEARUP herkent watcher-wrapped stale-plan fouten en voert maximaal drie verse dependency-audits uit binnen een 60-minuten fail-closed budget.
- Release-transition workerfouten worden persistent vastgelegd en legacy ownership-migratie is idempotent.
- Target identity: EnergieProject 32.4.55 / Projectmanager 2.0.0-rc42.
