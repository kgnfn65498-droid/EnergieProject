# Testinstructies v9.4.0

1. Commit/push v9.4.0, kies in Home Assistant **Opnieuw bouwen** en open de Web UI. Vóór certificering moet de app melden dat productiekern `9.4-core1` nog één productietest vereist; Recovery/Audit/API mogen geen fout tonen.
2. Voer één keer **Test automatische maandafsluiting nu** uit voor `2026-08`. Dit is de laatste verplichte volledige test zolang `PRODUCTION_CORE_REVISION` op `9.4-core1` blijft.
3. Controleer na afloop: Productieklaar, Scheduler Actief, Monitoring 0 fouten/0 wachtstatussen, Gezondheidsdashboard 100%, certificaatrelease v9.4.0 en productiekern `9.4-core1`. Bij een latere release met dezelfde productiekern moet de app zonder nieuwe maandafsluitingstest direct productieklaar blijven.
