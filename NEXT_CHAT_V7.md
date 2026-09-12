# Nieuwe-chat overdracht — EnergieProject 32.4.42

Actuele ontwikkellijn: 32.4.42 Projectmanager technische closure, gebouwd vanaf de exact geverifieerde 32.4.41-ZIP.

## Bindende werkwijze

- Eerst actuele overdracht/status lezen vóór ontwikkelen.
- Bestaande architectuur en releaseflow hergebruiken; geen nieuwe weg bedenken.
- Hoofdoorzaak eerst; TDD RED→GREEN; daarna volledige hertest.
- Als de exacte vorige geverifieerde release-ZIP niet beschikbaar is: **altijd Peter om die ZIP vragen**.
- GitHub, losse bronreconstructie of een alternatieve buildroot mag niet als vervangende buildbasis worden gebruikt.
- Productieplaatsing en productie-restarts blijven expliciet beschermd.
- Geen gebruikers-Terminal/sudo als normale ontwikkelstap.
- Handover moet actuele taak, stap, werkstand, open beslissingen, Development Build Contract en `01_UNIFIED_DEVELOPMENT_LEDGER.md`-context bevatten.

## 32.4.42 doel

Projectmanager eerst technisch groen:
1. Native MCP exact releasegebonden via bestaande control-plane;
2. taak/progress/werkstand/timing consistent;
3. `JA`/`AKKOORD` werkt alleen voor exact één geldige open beslissing;
4. nieuwe chat kan met `verder` vanaf de actuele PM-waarheid en ontwikkelregels hervatten.

Crash Recovery/CLEARUP zijn bewust uitgesteld en mogen de technische PM-status niet rood houden of automatisch als huidige PM-taak worden gestart.

Na echte live controle van 32.4.42 volgt pas de afgesproken vervolgfase.
