# Changelog

## 32.1.0 - Maandelijkse Energiehistorie Excel
- Bouwt na een geslaagde maandworkflow een schone Numbers-vriendelijke `Energie_verbruik_historie.xlsx` vanaf nul.
- Excel is een niet-destructieve sidecar: een buildfout laat workflowstatus en vorige geldige master intact.
- Hergebruikt alle volledig gevalideerde projectmaanden t/m de doelmaand; een nieuwe maand laat eerdere maanden dus niet verdwijnen.
- Kalenderjaar is de primaire dashboard- en jaarvergelijkingsbasis; contract-/afrekenjaren blijven apart.
- `VOLLEDIG` en `PARTIEEL` blijven expliciet; een lopende maand telt niet mee in gelijke-maandenvergelijkingen.
- Publiceert de master atomair en maakt voor een volledige maand een byte-identieke maandarchiefkopie.
- Voorkomt regressies naar de eerdere 2008-datumverschuiving en Excel-reparatiemelding door formulevrije schone XLSX-opbouw en ZIP/XML-validatie.
- Automatische maandafsluiting blijft uitgeschakeld; watcher-retenties en de NAS -> GitHub -> Home Assistant-publicatieketen blijven ongewijzigd.
