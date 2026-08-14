# Changelog

## 32.0.35 - Pagina 2 onbekende terugleververgoeding
- Pagina 2 accepteert een onbekende `feed_in_compensation` zonder TypeError.
- Onbekende terugleververgoeding blijft `Niet beschikbaar`; er wordt geen €0 gefabriceerd.
- Numerieke terugleververgoeding behoudt de bestaande negatieve presentatie.
- Geen wijziging aan SMP-fallback, maandworkflow, augustus, Crash Recovery of `finalize_month`.
