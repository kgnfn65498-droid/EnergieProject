# Testinstructies v9.3.0

1. Commit/push v9.3.0, kies in Home Assistant **Opnieuw bouwen**, start de app en controleer dat de Web UI normaal opent. Controleer onder **Historische runs** dat `Afgerond` als `dd-mm-jjjj uu:mm` wordt getoond en dat **Retry Debug v9.3.0** de regel **Legacy bronstatus (historisch)** toont.
2. Controleer Monitoring, Recovery en Auditintegriteit. Er mogen door deze release geen nieuwe foutstatussen ontstaan.
3. Alleen wanneer v9.3.0 als actieve gecertificeerde productieversie moet blijven draaien: voer één keer **Test automatische maandafsluiting nu** uit. Dit is niet opnieuw een test van het oude schedulerprobleem; het is uitsluitend nodig omdat het productiecertificaat momenteel exact versiegebonden is. Daarna moet certificaat `v9.3.0` geldig zijn en het Gezondheidsdashboard 100% tonen.
