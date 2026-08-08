# Nieuwe chat overdracht — EnergieProject na v10.4.2

## Startpunt
Gebruik de actuele NAS/GitHub-repository `EnergieProject` als enige ontwikkelbasis. De iMac is geen noodzakelijke schakel meer.

Actieve paden:
- NAS-master: `/share/Energie_NAS/EnergieProject`
- release-inbox: `/share/Energie_NAS/EnergieProject_Inbox`
- backups: `/share/Energie_NAS/EnergieProject_Backups`
- GitHub: `kgnfn65498-droid/EnergieProject`, branch `main`, SSH deploy key vanuit Home Assistant/Terminalomgeving.

## Bewezen vóór v10.4.2
- QNAP-share `AI Projecten` is vanuit Home Assistant lees-/schrijfbaar.
- NAS-repository en GitHub `main` kunnen zelfstandig fetchen/pushen zonder iMac.
- v10.3.1 heeft ZIP-validatie, volledige tar-backup, rollback, Git commit/push en GitHub-eindcontrole bewezen.
- v10.4.1 heeft self-safe installer/watcher buiten de live worktree geïnstalleerd.
- Release-watcher draait met interval 30 seconden.

## v10.4.2 doel
Bewijs dat alleen het plaatsen van een ZIP in `incoming` voldoende is. Geen Terminal-commando voor installatie. Bij succes moet ZIP automatisch via processing naar processed gaan en GitHub `main` automatisch worden bijgewerkt.

## Vaste afspraken
- Als gebruiker zegt `bouw X.Y`, daadwerkelijk een complete ZIP bouwen op de laatste bewezen versie.
- Iedere build: downloadbare ZIP, changelog, testresultaat en kopieerbare committekst.
- Geen gok-commando's; eerst bestaande platformmogelijkheden controleren.
- Recovery/crashherstel moet simpel en gedocumenteerd blijven.
- Productiekern `9.4-core1` blijft geldig totdat een inhoudelijke kernwijziging een nieuwe certificering vereist.
- Normale Home Assistant app-update/herstart blijft voorlopig handmatig; opnieuw opbouwen alleen bij aantoonbare noodzaak.
- GitHub Desktop/iMac zijn niet nodig voor de automatische NAS→GitHub-releaseketen.

## Vervolg v10.x na stabiele watcher
1. 24/7 watcher/persistent opstartgedrag na Home Assistant/add-on reboot bewijzen en automatiseren.
2. Weercontext en circa 14-daagse verwachting integreren voor proactieve verbruiks-/kostenwaarschuwingen.
3. Next Energy/dynamische prijsdata (incl. morgenprijzen wanneer beschikbaar) automatisch ophalen en historiseren.
4. Eén mobiel dashboard dat relevante informatie dynamisch prioriteert.
5. Financiële regie: termijnbedrag, jaarprognose, werkelijke kosten, historische vergelijking en betrouwbaarheid/bandbreedte.
6. Rendabele marktopties signaleren, doel terugverdientijd grofweg 5–6 jaar, met onderbouwde aannames.
7. Conversatie-/analysebasis waarmee vragen als kwartaalvergelijkingen en grafieken rechtstreeks uit de opgeslagen data beantwoord kunnen worden.
8. Recovery Manager reduceren tot calamiteiten/crash recovery met korte herstelhandleiding.

## Werkwijze nieuwe chat
Begin met de status van v10.4.2. Als watcher-test geslaagd is: behandel die versie als nieuwe stabiele basis en ga door met de resterende v10.x-roadmap.
