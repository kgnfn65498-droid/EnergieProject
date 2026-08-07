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


## Home Assistant-energiebronnen

Versie 4.5.0 leest bestaande Home Assistant-entiteiten:

```yaml
homeassistant_energy_sampling_enabled: true
homeassistant_energy_sample_seconds: 900
enphase_entity_id: "sensor.envoy_122335051406_lifetime_energy_production"
nordpool_entity_id: "sensor.nordpool_kwh_nl_eur_3_10_021"
nextenergy_entity_id: "sensor.nextenergy_actuele_stroomprijs"
```

De maandbestanden worden opgebouwd onder:

`/config/output/homeassistant_energy/YYYY_MM/`

Nord Pool en NextEnergy zijn aanvullende bronnen. De bestaande EPEX v6-module
blijft de officiële maandprijsbron totdat die afzonderlijk in de app is gekoppeld.


## Maandmap bouwen

De knop `Bouw maandmap` maakt:

`/config/output/01_Input/YYYY_MM/`

met de beschikbare HomeWizard-, Enphase- en prijsbestanden. Daarbij worden
dubbele tijdstempels verwijderd, Enphase MWh naar kWh omgerekend en negatieve
nulprijzen genormaliseerd.

De map bevat daarnaast:

- `month_input_validation.json`
- `month_input_manifest.json`

en er wordt een ZIP gemaakt als:

`/config/output/01_Input/01_Input_YYYY_MM.zip`


## EPEX import en validatie

Configureer de twee officiële v6-bronnen:

```yaml
epex_electricity_enabled: true
epex_electricity_url: "..."
epex_electricity_output_name: "EPEX stroom.csv"
epex_gas_enabled: true
epex_gas_url: "..."
epex_gas_output_name: "EPEX gas.csv"
epex_require_full_calendar_month: true
```

Klik daarna op `Importeer en valideer EPEX`. De app controleert de volledige
kalendermaand en schrijft de bestanden onder:

`/config/output/epex_monthdata/YYYY_MM/`


## Overdracht naar de projectomgeving

De knop `Maak overdrachtspakket` kopieert uitsluitend een volledig gevalideerde
maandmap naar:

`/share/Energie_Overdracht/YYYY_MM/`

Daarnaast worden geplaatst:

- `/share/Energie_Overdracht/01_Input_YYYY_MM.zip`
- `/share/Energie_Overdracht/Overdracht_YYYY_MM.json`

De echte NAS-map `Energie/01_Input/YYYY_MM` wordt in deze versie nog niet
rechtstreeks gewijzigd. Daarmee blijft de bestaande projectstructuur beschermd
tot de eindworkflow volledig is getest.


## Volledige maandworkflow

Klik op `Verwerk maanddata`. De workflow verwerkt standaard de vorige
kalendermaand en voert achtereenvolgens uit:

1. SlimmeMeterPortal API-test
2. SlimmeMeterPortal maandimport
3. HomeWizard-detectie
4. HomeWizard-snapshot
5. Home Assistant-energiesnapshot
6. EPEX, indien geconfigureerd
7. Maandmap bouwen en valideren
8. Overdrachtspakket maken
9. Home Assistant-notificatie

Het eindverslag staat onder:

`/config/output/workflow_results/YYYY_MM/workflow_result.json`


## Handmatige maandtest

De knop `Verwerk maanddata` bevat vanaf 5.0.2 een maandkeuze.

- Kies de huidige maand voor een directe functionele test met live snapshots.
- Een historische maand gebruikt uitsluitend de bestanden die tijdens die maand
  al zijn opgebouwd.
- De geplande productierun blijft bedoeld voor de vorige kalendermaand.


## Warning versus fout

Vanaf 5.0.3 geldt:

- `warning` is toegestaan wanneer alleen optionele bronnen ontbreken;
- niet-geconfigureerde EPEX-bestanden blokkeren de workflow niet;
- `missing_required` of `empty_required` blokkeert altijd;
- een geslaagde workflow met optionele ontbrekende bronnen eindigt als
  `status: warning`.


## Opnieuw uitvoeren van dezelfde maand

Vanaf 5.0.4 mag de volledige workflow dezelfde maand opnieuw verwerken. De app:

1. bouwt de nieuwe overdracht in een stagingmap;
2. controleert alle SHA-256-hashes;
3. bewaart de bestaande overdracht tijdelijk als backup;
4. vervangt map en ZIP;
5. herstelt automatisch de vorige versie wanneer iets mislukt.

De losse knop `Maak overdrachtspakket` blijft bewust niet-overschrijvend.


## Fase 7.0

- `automatic_month_close_enabled`: schakelt de automatische volledige maandafsluiting in. Standaard uit voor veilige ingebruikname.
- `automatic_month_close_day` en `automatic_month_close_hour`: uitvoermoment in tijdzone Europe/Amsterdam.
- Historische maanden kunnen in de webinterface expliciet worden gekozen. Daarbij worden geen actuele snapshots toegevoegd.
- `operation-status` toont de actieve workflow, laatste run, automatische afsluitstatus en recente maandresultaten.
- Definitieve bestanden blijven `Energierapport_YYYY_MM.pdf` en `Recovery_Update_YYYY_MM.zip`.

## Versie 7.3.6 — meldingen en automatische maandafsluiting

De volledige maandworkflow heeft eigen Home Assistant-meldingen. Met `workflow_notify_home_assistant` kunnen deze onafhankelijk van de overdrachtsmelding worden in- of uitgeschakeld. Met `workflow_notify_on_start` kan ook de start van een handmatige of automatische workflow worden gemeld. Tijdens de volledige workflow wordt de losse overdrachtsmelding onderdrukt, zodat één workflow niet meerdere tussentijdse "gereed"-meldingen veroorzaakt.

Voor de automatische maandafsluiting geldt een retry-beveiliging. Na een mislukte automatische run wacht de scheduler standaard `automatic_month_close_retry_hours: 6` voordat dezelfde maand opnieuw wordt geprobeerd. Een geslaagde maand wordt niet opnieuw verwerkt. De operationele status toont de trigger (`manual`, `historical`, `resume` of `automatic`) en, indien van toepassing, het eerstvolgende retrymoment.


## Versie 7.4.0 — broncoördinatie en eindvalidatie

De volledige maandworkflow voert vóór overdracht en rapportage een extra doelmaandgebonden eindvalidatie uit. Voor actuele maanden wordt een expliciet ingeschakelde externe Enphase-bron automatisch geïmporteerd. EPEX blijft automatisch meelopen wanneer geconfigureerd. Historische workflows halen geen actuele Enphase/HomeWizard-data op om oude maanden aan te vullen; zij blijven bronbeschikbaarheid-gestuurd. De eindvalidatie wordt opgeslagen als `workflow_results/YYYY_MM/pre_report_validation.json` en als `last_pre_report_validation` in de operationele status.


## Versie 7.5.0 — productieharde automatische maandafsluiting

Voor een automatische maandafsluiting voert de app eerst een preflight uit op configuratie, lokale schrijfbaarheid, overdrachtsmap en rapport-runtime. Bij een fout start de workflow niet en volgt een veilige retry. Na een automatische workflow controleert de finalization de pre-report-validatie, rapportgeneratie en de gepubliceerde `Energierapport_YYYY_MM.pdf` en `Recovery_Update_YYYY_MM.zip`.


## Versie 7.6.0 — bediening automatische maandafsluiting

De operationele console bevat nu een aparte kaart **Automatische maandafsluiting**. Daar kunnen Aan/Uit, dag, uur en retryperiode worden ingesteld. De knop **Test automatische maandafsluiting nu** voert een gecontroleerde productietest uit op een gekozen maand: preflight, echte maandworkflow en finalization. Deze test zet de schedulermaand niet op reeds verwerkt, zodat de reguliere automatische maandafsluiting later gewoon kan plaatsvinden.
