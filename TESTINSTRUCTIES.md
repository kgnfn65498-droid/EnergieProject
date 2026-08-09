# Testinstructies v10.5.33

1. Zet `EnergieProject_v10.5.33.zip` rechtstreeks in `EnergieProject_Inbox/incoming`.
2. Wacht op automatische verwerking naar `processed`.
3. Installeer de Home Assistant-update naar 10.5.33.
4. Download **analysedata** en **release-diagnose** en stuur beide hier.

Verwacht:
- versie 10.5.33;
- gewogen NextEnergy-analyse blijft `weighted_ok`;
- `financial_readiness` is aanwezig;
- `financial_readiness.progress_pct` is groter dan 0 maar `decision_ready=false`;
- `next_required_components` noemt minimaal vaste leverancierskosten, opslag, terugleververgoeding en gasformule;
- kandidaat 30-dagen variabele stroomkosten blijven beschikbaar voor validatie;
- `monthly_advance_eur = 150.0`;
- `advance_comparison_scope = variable_electricity_only_not_all_in`;
- geen leverancier-all-in prognose zolang contractcomponenten ontbreken;
- release-diagnose blijft zonder Terminal werken.

Juli-EPEX blijft `gedeeltelijk` t/m 2026-07-29.
Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
