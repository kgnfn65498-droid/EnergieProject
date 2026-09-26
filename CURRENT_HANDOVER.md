# CURRENT HANDOVER — EnergieProject 32.5.18

## Actuele ontwikkelpositie
- Exacte buildbasis: fysiek geaccepteerde 32.5.17 ZIP SHA256 `d86071a825f43d6c1c65368cf5d61782ed7df9c6dd26045c607adeed9af6670d`.
- 32.5.16 is live COMPLETE; 32.5.17 is bewust niet geïnstalleerd nadat de harde eis werd aangescherpt naar structurele eliminatie van de PM↔watcher single-slot result-mailbox.
- 32.5.18 vervangt die single-slot result-mailbox door een unieke, request-scoped result-path `Data/03_Systeem/Projectmanager/ClearUp/Runtime/results/<request_id>.json`.
- De privileged watcher accepteert alleen exact die request-id-gebonden result-path; mismatches, escapes en symlinks fail-closed.
- De vaste canonical result blijft alleen duurzame auditkopie nadat het request-scoped resultaat exact is gelezen. Hij is niet langer onderdeel van de synchronisatie/wachtlogica.
- Daardoor kan een stale inode/resultaat van een vorige Type-2 operatie de volgende PM-call niet meer blokkeren of vals laten time-outen.
- Geen destructive Type-2 finalize/delete vóór externe recoveryontvangst.

## Autonome vervolgroute na installatie
1. Controleer 32.5.18 COMPLETE 9/9, PM `2.0.0-rc51` en runtime readback.
2. Voer ClearUp_002 recovery refresh via echte ingress/consumer/privileged watcher uit en eis PM-resultaat GREEN zonder timeout.
3. Valideer ClearUp_002 live.
4. Refresh/deep-verify ClearUp_012; daarna 002–012 individueel deep-verify.
5. Download de echte 002–012 recovery-ZIPs naar de ChatGPT-workspace en verifieer lokaal size + SHA256.
6. Lever recovery-ZIPs aan Peter; destructive finalize/delete blijft geblokkeerd tot expliciete ontvangstbevestiging.

## Harde acceptatieregel
Type-2 is pas werkelijk 100% klaar na de live 32.5.18 PM↔watcher E2E en externe recovery-download. Offline test-GREEN alleen is geen eindclaim.
