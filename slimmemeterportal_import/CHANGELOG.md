# Changelog

## 32.4.32

- QNAP-side watcher bootstrap prepareert `EnergieProject/CLEARUP` als bestaande rootquarantaine vóór de HA CLEARUP-run; geen relocatie naar Inbox/Backups.
- CLEARUP controleert de quarantainebestemming vroeg op symlink, filesystem en runtime-schrijfbaarheid; permissiefouten blokkeren vóór zware hashes.
- 32.4.31 unreadable-candidate REVIEW-fix en alle bestaande CLEARUP safety-gates blijven intact.
