# Changelog

## 32.0.31 - Crash Recovery live-snapshot
- Structurele live-snapshot vervangt losse uitzonderingen voor runtime-heartbeats.
- Watcher- en scheduler-heartbeats kunnen tijdens een Crash Recovery normaal blijven doorlopen.
- Bestanden die tijdens hun eigen read wijzigen blijven streng afgekeurd en veroorzaken een veilige retry.
- Bestandsset wordt voor en na de snapshot gecontroleerd; nieuwe of verdwenen paden veroorzaken een veilige retry.
- Downloadnaam blijft filesystem-veilig: `YYYY-MM-DD HH.MM CrashRecovery EnergieProject.zip`.
