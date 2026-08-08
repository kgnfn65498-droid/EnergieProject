# Testinstructies v10.5.4

## Definitieve releaseketentest
1. Plaats uitsluitend `EnergieProject_v10.5.4.zip` in `EnergieProject_Inbox/incoming`.
2. Gebruik GEEN Home Assistant Terminal.
3. Gebruik GEEN handmatige Git-commit of Git-push.
4. Wacht tot de ZIP automatisch in `processed` staat.
5. Wacht daarna maximaal circa 1 minuut op de Home Assistant GitHub-publisher.
6. Open de Energieproject-console en controleer:
   - `HA-publicatie` = `Automatisch`;
   - laatste publicatie = `10.5.4`.
7. Controleer vervolgens in Home Assistant of v10.5.4 als add-onupdate verschijnt.
8. Installeer v10.5.4 via de normale knop `Bijwerken`.
9. Controleer na de update:
   - versie = `10.5.4`;
   - workflow = `idle`;
   - laatste run = `completed`;
   - releaseketen = `Automatisch`;
   - HA-publicatie = `Automatisch`.

## Geslaagd criterium
De test is alleen geslaagd wanneer stap 1 t/m 9 zonder Terminal, handmatige Git-commit of handmatige Git-push zijn uitgevoerd.
