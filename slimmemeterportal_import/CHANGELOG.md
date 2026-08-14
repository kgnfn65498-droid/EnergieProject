# Changelog

## 32.0.37 - Veilige automatische GitHub-publicatie
- Release-installer definieert de watcher-logmap expliciet; de v32.0.36 LOGDIR-regressie kan niet terugkomen.
- Projectshare wordt dynamisch gevonden na hernoemen naar Project Energie.
- Publicatie gebruikt uitsluitend de dedicated Git-worktree en een gevalideerd publication-contract.
- Onverwachte GitHub main-versie of manifest blokkeert de push; geen force-push.
- Automatische maandafsluiting blijft uitgeschakeld.
