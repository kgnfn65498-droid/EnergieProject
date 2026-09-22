# Changelog

## 32.4.61 — publisher delivery separation closure

- GitHub publication proof is now independent from Home Assistant delivery/update outcome.
- Replaced unsupported `/addons/self/rebuild` delivery with official store reload + asynchronous `/store/addons/<slug>/update`.
- Exact GitHub identity is preserved on HA delivery errors; ReleaseController can settle on exact GitHub + exact HA runtime.
- Added regressions for HTTP 400 delivery failure, exact settlement and native 9-phase successor lifecycle.

## 32.4.60 — combined autonomous publisher closure

- Publication delivery is exact identity-fenced; HA version alone cannot close delivery.
- ReleaseController owns exact publication-contract settlement.
- Processing remains transactional until delivery is proven COMPLETE.
- Completed predecessor settlement gates the next Incoming release.
- Corrected 32.4.58 c9d67 baseline and single Home Assistant config layout are enforced.
