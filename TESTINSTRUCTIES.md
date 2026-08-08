# Testinstructies v10.5.3

1. Plaats `EnergieProject_v10.5.3.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht tot de ZIP in `processed` staat.
3. Publiceer v10.5.3 nog één keer via de bestaande handmatige Home Assistant Git-route, omdat de automatische publisher van v10.5.2 nog niet aantoonbaar werkte.
4. Installeer v10.5.3 in Home Assistant.
5. Controleer direct na herstart het add-onlog. Verwacht minimaal:
   - `GitHub-publisher startup: enabled=True`
   - `GitHub-publisherthread gestart.`
   - `GitHub-publishercontrole: enabled=True`
   - daarna een publicatiepoging of melding dat de release al verwerkt is.
6. Open de Energieproject-console. De statuskaart `HA-publicatie` moet zichzelf binnen 15 seconden actualiseren zonder op de knop te hoeven klikken.
7. Als de status `Automatisch` wordt, bouw/test daarna v10.5.4 uitsluitend via `incoming`; v10.5.4 is de definitieve end-to-end test zonder Terminal.
