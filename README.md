# EnergieProject 32.4.42

32.4.42 richt zich uitsluitend op het technisch betrouwbaar afronden van Projectmanager V2. De bestaande architectuur en releaseketen blijven leidend; er wordt geen alternatieve ontwikkel- of publicatieroute toegevoegd.

Kernpunten:

- Projectmanager-technische gereedheid wordt apart gemeten van uitgestelde Crash Recovery/CLEARUP-projectafsluiting;
- stale release-ingresstaken worden runtime-first en smal/machine-verifieerbaar verzoend;
- timing, ETA en Development Build Contract blijven verplicht zichtbaar;
- Native MCP reload blijft via de bestaande `energie-control-plane` en is hard gebonden aan actuele release, command en beslissing;
- Chat/Voice/Nomad kan `JA` of `AKKOORD` gebruiken wanneer exact één passende Projectmanager-goedkeuring openstaat;
- nieuwe-chat-overdracht bevat actuele taak, stap, werkstand, open beslissingen, development context, ledgerverwijzing en buildcontract;
- als de exacte vorige geverifieerde release-ZIP niet beschikbaar is, wordt Peter altijd om die ZIP gevraagd; GitHub of reconstructie mag niet als vervangende buildbasis worden gebruikt.

De normale installatie blijft: exact geverifieerde ZIP → Home Assistant/QNAP `Incoming` → watcher → live controle. Productieplaatsing en productie-restarts blijven beschermd.
