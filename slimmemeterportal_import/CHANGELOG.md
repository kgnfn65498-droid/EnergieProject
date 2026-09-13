# Changelog

## 32.4.49
- Native-MCP root-cause closure: exact release-bound self-heal can safely authorize during LIVE_ACCEPTANCE under policy v2 when all release checks except PM self-audit are green.
- Projectmanager self-audit recomputes active build-contract compliance instead of treating the static contract definition as a failed result.
- Existing protected-action boundaries and the accepted-release path remain fail-closed.
