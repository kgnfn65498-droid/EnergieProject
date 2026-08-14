# Changelog

## 32.0.34 - SMP analyse/rapport-fallback
- Volledige SlimmeMeterPortal-dekking kan netafname, teruglevering en gas leveren wanneer historische P1/P1g-detaildata ontbreekt.
- P1/P1g blijft per metriek leidend; SMP wordt nooit op dezelfde metriek opgeteld.
- Analyse en rapportadapter gebruiken dezelfde bronselectie en tonen de gekozen bron.
- Historische rapportage wordt niet meer overgeslagen alleen door ontbrekende HomeWizard/socket/Enphase-detailbestanden wanneer de SMP-kernmetriek volledig is.
- Succesvolle rapportuitvoer wordt atomair gepubliceerd naar `Data/02_Output/Rapportages/YYYY_MM`, inclusief `2026_07`.
- De gerichte actie `Herbouw historisch rapport` repareert rapportage zonder de maandworkflow opnieuw te starten.
- Geen wijziging aan augustus 2026, automatische maandafsluiting, Crash Recovery, NextEnergy of `finalize_month`.
