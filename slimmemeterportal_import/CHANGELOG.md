# Changelog

## 32.4.31

- CLEARUP behandelt een onleesbare historische kandidaat fail-closed als `REVIEW` in plaats van de volledige post-release run te laten crashen.
- Onleesbare kandidaten krijgen expliciet `candidate_read_error`-bewijs en geen vertrouwde tree-hash; zij worden nooit gemoved. Andere bewezen veilige kandidaten behouden de bestaande reversibele same-filesystem hard-rename route.
- `ClearupExecutionTimeout`, dependency/symlink-audit, bronhash, rollback, manifest en no-delete veiligheidsgrenzen blijven ongewijzigd.
- Nieuwe chats mogen ontwerpen en ontwikkelen, maar alle bestaande en toekomstige ontwikkelregels en platformconstraints blijven verplicht over chatgrenzen heen.
- QNAP-host `python3` is geen toegestane vaste dependency; Python-taken op de NAS lopen via de afgesproken container/runtime.
- Core blijft `9.4-core3`, PM blijft `2.0.0-rc22`.
