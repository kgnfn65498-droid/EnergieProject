# Changelog

## 32.5.20

- Native MCP Type-2 recovery export accepteert cryptografisch geverifieerde zero-byte payloads correct als `size=0` in plaats van ze foutief als `-1` af te keuren.
- De release-hotfix source-of-truth publiceert dezelfde gecorrigeerde verifier naar de canonieke Native-MCP runtimebron.
- Geen Type-2 migrate, finalize of delete wordt door deze release uitgevoerd.
