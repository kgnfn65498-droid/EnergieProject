# Changelog

## 24.0.0
- Start v24 met een guarded Action Handoff Runtime bovenop de gevalideerde v23-portfolio/publicatieketen.
- Alleen een volledig publiceerbare, positieve en traceerbare v23-case kan `ready_for_user_action` worden.
- De handoff voert nooit zelfstandig een aankoop, contractwissel of apparaatsturing uit; externe actie vereist gebruikerbevestiging.
- Geblokkeerde cases blijven `waiting_for_data`; ontbrekende financiële waarden blijven `Niet beschikbaar` en nooit €0.
- Roadmap v24: stap 1/5; volgende stap is guarded action tracking.
