# Changelog

## 32.3.36

- Historische rapportherbouw draait asynchroon zodat Home Assistant Ingress niet op één lange POST hoeft te wachten.
- De console pollt status en navigeert automatisch naar succes/fout; refresh herstelt de actieve knopstatus.
- Dubbele herbouw wordt geblokkeerd met een aparte lock.
- De v32 final-validation gate wordt dynamisch bepaald uit live HA-bereikbaarheid en release-identiteit.
