# Changelog

## 32.4.26 — indexed CLEARUP dependency audit

- CLEARUP leest actieve tekstbestanden en inventariseert symlinks voortaan één keer per plan in plaats van opnieuw per kandidaat.
- Fail-closed dependencyregels, kandidaat-tree-hashes, harde same-filesystem move en herstelmanifest blijven inhoudelijk gelijk.
- Deze release repareert uitsluitend de live performancegrens van 32.4.25; productiekern blijft `9.4-core3` en PM blijft `2.0.0-rc22`.
