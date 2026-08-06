# SlimmeMeterPortal Import v3.1.0

## Eerste configuratie

1. Vul de officiële API-key in.
2. Zet `schedule_enabled` tijdens de eerste proef op `false`.
3. Start de app.
4. Open de webinterface.
5. Klik eerst **Test API-verbinding**.
6. Kies daarna één kalendermaand en klik **Importeer nu**.

## Automatisch

Na een geslaagde proef:

- `schedule_enabled: true`
- `schedule_day: 2`
- `schedule_hour: 3`

De app verwerkt iedere maand de vorige kalendermaand.

## Uitvoer

De app bewaart data onder:

`/addon_configs/slimmemeterportal_import/output/YYYY_MM/`

Elke maand bevat:

- `connections.json`
- `raw/*.json`
- CSV per aansluiting
- JSONL per aansluiting
- `validation_report.json`

De webinterface kan iedere verwerkte maand als ZIP downloaden.

## Status

- `/health` geeft een eenvoudige healthcheck.
- `/status.json` geeft de technische status.


## Hervatten en retentie

- `resume_incomplete_month: true` hergebruikt reeds opgehaalde dagbestanden.
- `retention_months` bepaalt hoeveel maandmappen lokaal bewaard blijven.
- Tijdens een lopende import staat `.incomplete` in de maandmap.
- Iedere afgeronde maand bevat `manifest.json` met SHA-256 hashes.

## Annuleren

Gebruik **Annuleer actieve import** in de webinterface. De import stopt na de
lopende API-aanroep en behoudt de reeds opgehaalde dagbestanden voor hervatting.


## Integriteitscontrole

- `verify_after_import: true` controleert na iedere import alle bestanden tegen
  `manifest.json`.
- Het resultaat staat in `integrity_report.json`.
- Met **Controleer laatste maand** kan de nieuwste maand opnieuw worden gecontroleerd.
- `fail_on_validation_errors: true` laat de app de import als fout markeren zodra
  het validatierapport fouten bevat.


## Duplicaten en maandsamenvatting

- `detect_duplicates: true` telt exact dubbele records per aansluiting.
- `create_month_summary: true` maakt `month_summary.json`.
- Numerieke velden worden automatisch samengevat met aantal, som, minimum,
  maximum en gemiddelde.
- Dubbele records worden als waarschuwing opgenomen in `validation_report.json`.


## Workflowmodus

- `workflow_mode: smp_only` verwerkt alleen SlimmeMeterPortal.
- `workflow_mode: full_month_workflow` activeert de centrale bronstatus voor:
  HomeWizard, Enphase, EPEX elektriciteit en EPEX gas.
- Nog niet geconfigureerde bronnen worden expliciet als `not_configured`
  weergegeven en niet stilzwijgend als succesvol behandeld.

## Overdrachtspakket

Met `create_transfer_bundle: true` ontstaat na iedere afgeronde import:

`Energie_Maandimport_YYYY_MM.zip`

Dit pakket bevat de volledige maandmap en is bedoeld als gestandaardiseerde
overdracht naar de uiteindelijke projectopslag.


## HomeWizard

Activeer HomeWizard met:

```yaml
homewizard_enabled: true
homewizard_sample_seconds: 900
homewizard_devices:
  - label: "P1"
    host: "192.168.1.x"
    role: "p1"
    optional: false
  - label: "Airco"
    host: "192.168.1.y"
    role: "socket"
    optional: false
```

De app gebruikt uitsluitend de lokale HomeWizard-endpoint:

`http://<host>/api/v1/data`

Snapshots worden opgeslagen onder:

`/addon_configs/slimmemeterportal_import/output/homewizard_snapshots/YYYY_MM/`

Optionele apparaten veroorzaken een waarschuwing; verplichte apparaten een fout.


## Enphase en EPEX

De adapters gebruiken configureerbare HTTPS-bronnen.

```yaml
enphase_enabled: true
enphase_source_url: "https://..."
enphase_bearer_token: ""

epex_electricity_enabled: true
epex_electricity_url: "https://..."

epex_gas_enabled: true
epex_gas_url: "https://..."
```

De broninhoud wordt ongewijzigd opgeslagen als JSON, CSV of BIN onder:

`/addon_configs/slimmemeterportal_import/output/external_sources/`

De exacte officiële bron-URL's en eventuele Enphase-token worden pas ingevuld
wanneer die beschikbaar zijn; ontbrekende configuratie wordt expliciet gemeld.


## Centrale maandvalidatie

Na een maandimport wordt `central_validation.json` gemaakt. Deze controleert:

- SlimmeMeterPortal-resultaat;
- HomeWizard, wanneer ingeschakeld;
- Enphase, wanneer ingeschakeld;
- EPEX elektriciteit, wanneer ingeschakeld;
- EPEX gas, wanneer ingeschakeld.

Met `require_all_core_sources: true` moet iedere ingeschakelde kernbron werkelijk
een recente import of snapshot hebben.

## Rapporttrigger

```yaml
report_trigger_enabled: true
report_trigger_url: "https://..."
report_trigger_token: ""
```

Alleen wanneer de centrale validatie `ok` is, wordt een HTTP POST verstuurd met:

- jaar;
- maand;
- overdrachtspakket;
- centrale validatie.

Het resultaat staat in `report_trigger_result.json`.


## Zelftest

Gebruik **Voer volledige zelftest uit** na installatie of update.

De zelftest controleert:

- configuratie;
- schrijfrechten;
- SlimmeMeterPortal API;
- workflowbronnen;
- rapporttriggerconfiguratie.

`Installatie gereed: Ja` betekent dat geen blokkerende fout is gevonden.


## UserAPI-pad

De standaardinstelling is:

```yaml
usage_path_template: "/userapi/v1/connections/{connection_id}/usage/{date}"
```

De placeholders `{connection_id}` en `{date}` zijn verplicht. Hierdoor kan een
gewijzigd officieel endpoint worden ingesteld zonder een nieuwe appversie te bouwen.


## HomeWizard automatische metingen

De lokale HomeWizard API levert alleen actuele metingen en geen historische reeks.
Daarom verzamelt versie 4.1.0 vanaf het moment van activeren periodiek een snapshot.

Voorbeeldconfiguratie:

```yaml
homewizard_enabled: true
homewizard_sample_seconds: 900
homewizard_devices:
  - label: "P1"
    host: "192.168.2.10"
    role: "p1"
    optional: false
    output_name: "P1e.csv"
  - label: "Airco"
    host: "192.168.2.11"
    role: "socket"
    optional: false
    output_name: "Airco Skt.csv"
```

De bestanden worden per kalendermaand opgebouwd onder:

`/config/output/homewizard_monthdata/YYYY_MM/`

De app hernoemt geen bestaande bestanden. `output_name` wordt exact en
case-sensitive gebruikt.


## HomeWizard-detectie

```yaml
homewizard_discovery_enabled: true
homewizard_discovery_cidr: ""
homewizard_discovery_timeout_seconds: 1
```

Een lege CIDR-instelling laat de app het lokale `/24`-netwerk bepalen. De scan
blijft altijd beperkt tot één IPv4-/24-netwerk. De detectie maakt alleen een
voorstel en wijzigt de bestaande apparaatconfiguratie niet automatisch.


## HomeWizard-netwerk

Voor deze installatie is het standaard scanbereik:

```yaml
homewizard_discovery_cidr: "192.168.1.0/24"
```

Het interne Home Assistant-bereik `172.30.0.0/16` wordt nooit als
HomeWizard-thuisnetwerk gebruikt. Pas het CIDR alleen aan als het lokale netwerk
later wijzigt.


## Home Assistant-namen als vaste koppeling

Na HomeWizard-detectie leest de app de Home Assistant-entiteiten via de interne
Core API. De bestaande Home Assistant-naam wordt gebruikt voor de rapportnaam.
Het HomeWizard-serienummer is de vaste technische identiteit. Het IP-adres mag
door DHCP wijzigen; een nieuwe detectiescan actualiseert het bereikadres.

De mapping wordt opgeslagen in:

`/data/homewizard_mapping.json`
