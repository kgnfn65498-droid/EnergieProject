# CURRENT HANDOVER — EnergieProject 32.5.14

## 32.5.14 — control-plane stale-bind herstel

- Buildbasis: exact `EnergieProject_v32.5.13.zip`, SHA256 `dee215af80e17ddd379d35755849f2358d6df831a9f6a9a05d218e0cad5e17af`.
- 32.5.13 is live/ACCEPTED, maar de release-scoped Native-MCP reload werd geannuleerd doordat de control-plane `App/VERSIE.txt` als los Docker-bestand bind-mounted heeft. Na de atomic App-directoryswap bleef die mount naar de predecessor-inode wijzen en zag de control-plane 32.5.12.
- 32.5.14 wijzigt geen paden of services. Voor uitsluitend `energie_control_plane_release_request_v1` wordt de bestaande `Inbox/release_controller/current.json` + `Inbox/atomic_app_swap_state.json` gebruikt als release-autoriteit.
- Legacy/manual Native-MCP reloads behouden de bestaande `VERSIE.txt`-controle en expliciete Peter-approvalroute.
- Type-2 recovery-ZIP's blijven exact onder `Data/03_Systeem/Projectmanager/ClearUp/Exports`.
- Gate blijft `Data/03_Systeem/Projectmanager/ClearUp/State/TYPE2_EXTERNAL_RECOVERY_GATE.json`; delete/finalize blijft verboden totdat 002–012 buiten de NAS zijn gedownload, SHA-gecontroleerd en Peter bezit bevestigt.
- 32.5.13 downloadfunctionaliteit via de bestaande `projectmanager_status`-route blijft behouden; 32.5.14 repareert alleen de live Native-MCP activatie die daarvoor nodig is.

## Na live installatie
1. Controleer `App/VERSIE.txt = 32.5.14` en atomic `ACCEPTED`.
2. Controleer control-plane runtime/current en de release-scoped Native-MCP reload tot de runtimefingerprint exact GREEN is.
3. Roep de bestaande `projectmanager_status`-route aan en verifieer dat de Type-2 recovery-downloadlinks voor 002–012 zichtbaar zijn.
4. Download de echte recovery-ZIP's, verifieer SHA/ZIP-integriteit en lever ze in chat.
5. Pas daarna, na expliciete bevestiging van Peter, mag Type-2 finalize/delete verder.
