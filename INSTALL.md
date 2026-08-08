# Installatie / praktijktest v10.4.5

## Belangrijk: eenmalige bootstrap
De actieve productiebasis is na de mislukte v10.4.4-poging teruggevallen op de oudere installer. Die oudere installer kan v10.4.5 niet zelfstandig bootstrappen. Daarom is voor v10.4.5 één eenmalige bootstrap nodig via het meegeleverde `BOOTSTRAP_v10.4.5.sh`-bestand. Na succesvolle installatie moeten normale volgende releases weer uitsluitend als ZIP in `incoming` kunnen worden geplaatst.

## Doelresultaat
- v10.4.5 wordt geïnstalleerd zonder `git` en zonder metadata-/timestamp-preservering op de QNAP-share.
- De release-ZIP eindigt in `processed`.
- `VERSIE.txt` bevat `10.4.5`.
- De QNAP-watcher start daarna weer automatisch via de bestaande cronconfiguratie en controleert iedere 5 seconden.
- Bestaande failed-releases blijven ongemoeid.
