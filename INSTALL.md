# Installatie — EnergieProject 32.4.42

## Normale releaseflow

32.4.42 gebruikt uitsluitend de bestaande veilige releaseketen. De geverifieerde `EnergieProject_v32.4.42.zip` gaat via Home Assistant/QNAP `Incoming`, waarna de bestaande watcher de release verwerkt. Geen Terminal-, sudo-, GitHub-build- of alternatieve publicatieroute.

## Buildbasis

32.4.42 is gebouwd vanaf de exact geverifieerde 32.4.41-ZIP met SHA256 `5e8ccebb98eb269a688e7c8b67971956bfc63d2151d3024d630eabf120b170ff`. Als bij een volgende build de exacte vorige ZIP niet beschikbaar is, moet eerst Peter om die ZIP worden gevraagd; niet reconstrueren of een andere bron als bouwbasis nemen.

## Live controle na installatie

Eerst Projectmanager-technische closure bewijzen: identiteit, watcher/control-plane, Native MCP runtime, taak/progress/timing, chat/spraak-goedkeuring en nieuwe-chat-overdracht. Crash Recovery/CLEARUP zijn bewust een aparte, later te hervatten projectafsluitfase.
