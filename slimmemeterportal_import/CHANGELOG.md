# Changelog

## 32.4.21 — self-audit provenance closure

- Vervangt onbetrouwbare audit/status mtime-volgorde door expliciete `status_updated_at` provenance.
- Release-hold kan daardoor niet meer circulair blijven hangen op een self-audit die in dezelfde PM-cyclus net vóór status is geschreven.
- Watcher/SMB-heartbeatcontracten uit 32.4.20 zijn nu daadwerkelijk geïmplementeerd: stabiele inode en canonieke `watcher_heartbeat.v2`.
- Projectmanager V2 2.0.0-rc18.
