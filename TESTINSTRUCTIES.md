# Testinstructies v10.1.0

1. Commit/push v10.1.0, kies in Home Assistant **Opnieuw bouwen**, start de app en controleer bovenaan **versie 10.1.0**. De productiekern blijft `9.4-core1`; er is daarom geen nieuwe volledige automatische maandafsluitingstest nodig.
2. Controleer de nieuwe kaart **24/7 infrastructuur**. Als de QNAP-share al als Home Assistant netwerklocatie type **Share** met naam `Energie_NAS` gekoppeld is, moet de status `ok` zijn. Is dat nog niet ingesteld, dan mag `setup_required` verschijnen; dat is geen releasefout.
3. Klik **Download diagnosepakket** en stuur mij die ZIP. Klik daarnaast één keer **Download chat-overdracht** en controleer alleen dat de ZIP downloadt. Stuur de chat-overdracht alleen mee als die knop fout geeft.

Goedkeuringscriteria: `beoordeling.json` blijft `GO`, healthscore 100%, monitoring/recovery/audit blijven OK en `infrastructure_status.json` is aanwezig. QNAP `setup_required` is in v10.1 toegestaan totdat de eenmalige Home Assistant netwerkshare-configuratie is gedaan.
