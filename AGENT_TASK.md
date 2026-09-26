# AGENT_TASK — EnergieProject 32.5.23

- task_id: V32523-TYPE2-CONTROL-PLANE-PREPARE-2026-09-26
- mode: DEVELOPMENT
- thinking: HIGH
- owner: ChatGPT/Spock
- step: 1/1
- production_authority: NO

## Doel
Sluit de laatste live Type-2 blocker structureel: na Type-2 path activation moet de releasecontroller de daadwerkelijke `energie-control-plane` containerbinding bewijzen/repareren, óók wanneer Native MCP al current is. Hierdoor kan ClearUp_007 na installatie quiescent/GREEN worden zonder Peter als terminal- of Container Station-transportlaag.

## Scope
- exacte fysieke 32.5.22 ZIP als enige buildbasis;
- `NativeRuntimeCoordinator.align()` laat voor 32.5.23+ exact één control-plane prepare/binding-proof per release fence uitvoeren vóór de `native_mcp_current` shortcut;
- bestaande `ensure_control_plane_current()` / bounded binding recreate uit 32.5.22 hergebruiken; geen tweede actuatorroute;
- fail-closed op ontbrekende/RED/unproven binding evidence;
- na proces-reexec mag dezelfde COMPLETE release eenmaal opnieuw worden bewezen, daarna idempotent binnen dezelfde runtime;
- regressietests voor ready-Native-MCP + legacy control-plane binding, failure en idempotentie.

## Niet wijzigen
- geen nieuwe lifecycle-owner, watcher of publisher;
- geen automatische HA-installatie/restart;
- geen NAS reboot/restart;
- geen Type-2 finalize/delete tijdens build/audit;
- geen handmatige productie-statefabricage;
- geen terminalstap voor Peter.

## Bewezen feiten
- live 32.5.22 is COMPLETE 9/9, NAS/HA 32.5.22, PM rc55;
- ClearUp_005 en 006 zijn GREEN;
- ClearUp_007 blijft RED omdat live `energie-control-plane` nog legacy `Inbox/control_plane` schrijft;
- 32.5.22 `ensure_control_plane_current()` detecteert/repareert die binding correct wanneer aangeroepen;
- 32.5.22 `NativeRuntimeCoordinator.align()` roept prepare niet aan wanneer Native MCP guard al ready is.

## Acceptatie
- nieuwe regressie RED op exact 32.5.22 gedrag en GREEN na fix;
- 32.5.23+ ready-Native-MCP pad bewijst prepare/binding vóór shortcut;
- prepare-failure blokkeert fail-closed;
- dezelfde release fence prepare maximaal eenmaal per proces;
- oudere releasegedragingen blijven compatibel;
- volledige 32.5-suite GREEN;
- static suite GREEN;
- exact physical ZIP fresh-extract GREEN;
- exacte 32.5.22→32.5.23 atomic simulatie GREEN;
- artifact CRC/MANIFEST/SHA256SUMS/release-identiteit GREEN.

## Stopcriteria
Alleen stoppen bij echte safety/artifact blocker of wanneer definitieve geverifieerde ZIP gereed is. Geen productieactie in deze taak.
