# Installatie — EnergieProject 32.4.41

## Normale releaseflow

32.4.41 gebruikt de bestaande veilige releaseketen. De uiteindelijke, geverifieerde `EnergieProject_v32.4.41.zip` wordt via de normale Home Assistant/QNAP release-ingress geïnstalleerd; geen Terminal-, sudo- of handmatige Docker-commando's.

## Dedicated control-plane

De eenmalige Container Station-bootstrap van `energie-control-plane` is een infrastructuurvoorwaarde en staat los van het installeren van de 32.4.41-ZIP. De container gebruikt geen netwerkpoort en voert uitsluitend de exact goedgekeurde acties `watcher_recreate` en `native_mcp_reload` uit via de lokale Docker Unix-socket.

## Live acceptance na installatie

Een installatie geldt pas als live bewezen wanneer release-identiteit, watcher-contract, Native MCP-runtimefingerprint, actuele Crash Recovery-sets, CLEARUP/hygiëne, release-hold en atomic state via runtime-readback groen zijn. Een beschermde productieactie blijft expliciet approval-gated.
