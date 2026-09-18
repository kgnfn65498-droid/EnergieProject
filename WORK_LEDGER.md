# WORK_LEDGER — 32.4.56

## 2026-09-18 — rc43 → rc44
- Oude aangeleverde 32.4.56-ZIP geclassificeerd als rc43 read-only referentie; niet als release gepromoveerd.
- rc43 verzamelde 1.852 tests.
- Nieuwe rc44 live-rescue regressieset voegde exact 16 tests toe; totaal 1.868 tests.
- TDD-baseline bewezen: 16/16 nieuwe tests RED vóór implementatie.
- Structurele implementatie uitgevoerd voor publication permissions/rebuild, transition-ticket settlement, PROJECT_CR MAINTENANCE bridge, CLEARUP retry/hashcache, Project-CR deep-verify-efficiëntie, CR snapshot-scope, stale worker recovery en persistente continuïteitsdocumenten.
- Bestaande 32.4.56 process-workspace/root-hygiene/keep-1/startup-recovery behouden; niet opnieuw ontworpen.
- PROJECT_CR stale-marker recovery = 30 minuten; watcher executor timeout = 20 minuten; 10 minuten veiligheidsmarge.
- Broad-health race gesloten: executorresultaat wordt exact aan generation/phase/revision/ticket gebonden en settlement markeert de bewezen fase in `completed_phases` vóór doorgang.
- Historische Project-CR mockfixture aangepast aan het strengere onafhankelijke SHA/ZIP-readbackcontract; productiecontrole is niet versoepeld.
- `NEXT_CHAT_V7.md` verwijderd; PROJECT_CONSTITUTION.md, CURRENT_HANDOVER.md en WORK_LEDGER.md zijn de persistente nieuwe-chatlagen.
- Geen productieactie uitgevoerd tijdens build.

## Testbewijs vóór finale document-sync
- Nieuwe live-rescue regressies: 16/16 GREEN.
- Volledige `test_v32456_*` familie: 39/39 GREEN.
- Relevante historische transition/32.4.55/CR-regressies GREEN.
- Volledige collectie: 1.868 tests.
- Volledige regressie in gesplitste, time-outbestendige batches: 1.866 passed, 2 skipped, 0 failed.
- Eerste canonical artifact telde exact 494 ZIP-members en doorstond dezelfde fresh-extract regressie volledig; daarna is uitsluitend deze handover/ledger-eindstatus bijgewerkt.

## Finale acceptatiegates
- [x] 16/16 nieuwe regressies GREEN.
- [x] 39/39 32.4.56-familie GREEN.
- [x] volledige 1.868-test suite GREEN (1.866 passed, 2 skipped).
- [x] finale canonical ZIP na deze laatste document-sync: manifest + SHA256SUMS + CRC GREEN (exacte SHA in externe werklog).
- [x] finale exact-ZIP fresh-extract: 1.866 passed, 2 skipped, 0 failed (bewijs in externe werklog).
- [ ] daarna live end-to-end releaseacceptatie, uitsluitend na expliciete productieautoriteit.
