# Changelog

## 32.4.53 — technische 32.4 live-closure hardening

- NAS Container CR mailboxcontract structureel cross-runtime gemaakt: watcher/bootstrap zijn eigenaar van directory- en lockcontract; PM valideert uitsluitend en faalt gesloten bij drift.
- Atomische mailboxwrites gebruiken onvoorspelbare exclusieve, symlink-veilige tempfiles met finale 0644 readback.
- NAS Container CR is single-flight over watcher-restarts via watcher-owned `Inbox/.nas-container-cr.operation.lock`; QNAP bind-mount `flock` wordt live door capability-probe bewezen.
- Native CR snapshot-hotfix is uniek op de filename-loop begrensd en behoudt strikte temp-policy / fail-closed reguliere ENOENT.
- Post-release MAINTENANCE is tijdelijk tijdens actieve DEVELOPMENT-session en herstelt releasegebonden pas na groene closure.
- Target identity: EnergieProject 32.4.53 / Projectmanager 2.0.0-rc40.
- Codex onafhankelijke review: A/B/C/D alle vier PROVEN vóór finale regressie.
