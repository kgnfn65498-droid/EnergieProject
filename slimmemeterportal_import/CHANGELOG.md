# Changelog

## 32.1.1 - Maandelijkse Energiehistorie Excel startup-bootstrap
- Bouwt bij app-start automatisch de eerste schone `Energie_verbruik_historie.xlsx` als de master nog ontbreekt.
- Kiest de nieuwste volledig gevalideerde maand; op de huidige historie is dat juli 2026.
- Maakt tegelijk het ontbrekende maandarchief, zonder een maandworkflow of maandafsluiting te starten.
- Is idempotent en fail-safe: een bestaande geldige master blijft intact.
