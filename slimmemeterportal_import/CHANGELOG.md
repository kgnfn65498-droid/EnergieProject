# Changelog

## 23.3.0
- Portfolio Selection Runtime toegevoegd.
- Alleen de nummer 1 volledig gevalideerde positieve besparingskans kan als actie worden geselecteerd.
- Geblokkeerde domeinen en `validated_no_action` kunnen nooit als besparingsactie worden gekozen.
- Bij ontbreken van een valide kans blijft de uitkomst `wait_for_data` of `keep_current`.
- Nieuwe gevalideerde data triggert automatische herselectie.
