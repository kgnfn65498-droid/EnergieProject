# Changelog

## 32.4.60 — combined autonomous publisher closure

- Publication delivery is exact identity-fenced; HA version alone cannot close delivery.
- ReleaseController owns exact publication-contract settlement.
- Processing remains transactional until delivery is proven COMPLETE.
- Completed predecessor settlement gates the next Incoming release.
- Corrected 32.4.58 c9d67 baseline and single Home Assistant config layout are enforced.
