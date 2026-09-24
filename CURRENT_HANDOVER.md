# CURRENT HANDOVER — EnergieProject 32.5.5

Datum: 2026-09-24
Documentrol: statische release-handover voor artifact 32.5.5. Mutable live-status staat niet in dit document.

## Runtime-statusautoriteit
Actuele lifecycle/status komt uitsluitend uit:
- `Inbox/release_controller/current.json`;
- `Inbox/release_controller/runtime.json`;
- `Inbox/ha_runtime/current.json`;
- `Inbox/github_publication_state.json`;
- `Inbox/release_controller/post_live_audit.json` na COMPLETE.

## Aanleiding
32.5.3 kon GitHub en Home Assistant al bereiken terwijl de centrale App na een installatiefout terugrolde naar 32.5.2. Daardoor ontstond een legitieme maar niet gemodelleerde split-state. 32.5.4 kon alleen met noodpatches uit die toestand komen. Die noodroute is geen acceptabele normale werkwijze.

## 32.5.5 oplossing
- releasecontract bevat afzonderlijke `install_predecessor_*` en `publication_predecessor_*` identiteiten;
- de legacy predecessorvelden blijven compatibel maar vertegenwoordigen expliciet de publicatiepredecessor;
- Home Assistant publisher bewijst in split-state de lokale installatiepredecessor én de canonieke GitHub/HA-publicatiepredecessor afzonderlijk;
- exact gepubliceerde targetcontracten worden na lokale installatie niet opnieuw uit de gewijzigde App afgeleid;
- een bewezen rolled-back stale contract kan fail-closed en idempotent worden gearchiveerd; onbewezen state blijft geblokkeerd;
- split-state recovery blijft duurzaam WAITING op de canonieke publisher in plaats van te verlopen op een oude phase-clock;
- COMPLETE schrijft automatisch een machineleesbare post-live audit;
- settled IDLE wordt als gezonde rusttoestand behandeld;
- geen tijdelijke lokale versie-impersonatie, directe JSON-state-edit, containerrestart of PATCH/RECOVER-script is onderdeel van de normale 32.5.5 releaseketen.

## Releasecontract
`Incoming → Processing → pre-target contract → GitHub exact → atomic App target → ACCEPTED/WAITING_MANUAL_HA_UPDATE → handmatige HA-update → HA exact → contract settlement → Processed → COMPLETE → post-live audit → IDLE`.

## Safety
Productiecontainer restart, directe live App/state-mutatie, tijdelijke RW-container mounts, directe NAS-Git-publicatie en live PATCH/RECOVER-hotpatches zijn gevaarlijke acties. Zij mogen niet uit een algemene opdracht zoals “verder” worden afgeleid en vereisen Peters expliciete toestemming voor exact die actie.
