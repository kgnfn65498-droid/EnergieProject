# Changelog

## 32.4.27 — CLEARUP hash-I/O closure

- Verwijdert de dubbele volledige plan-hashpass uit de CLEARUP-applyfase, maar herhaalt vlak vóór de move wel de volledige dependency/symlink-audit.
- Elke CLEARUP-kandidaat wordt nog één keer direct vóór de harde rename volledig gehasht; dezelfde-filesystem rename wordt daarna via device/inode/size en old-path-absent geverifieerd.
- Geen wijziging aan protected/REVIEW/no-delete/restore-regels; core blijft `9.4-core3`, PM blijft `2.0.0-rc22`.
