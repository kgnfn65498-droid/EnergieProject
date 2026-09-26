## 32.5.23
- Release runtime alignment now proves the active control-plane container binding before accepting an already-current Native MCP runtime.
- Binding prepare is once-per-release-fence and fail-closed; the existing bounded 32.5.22 recreate/rollback implementation is reused.
- PM version rc56.

## 32.5.22
- Type-2 control-plane runtime binding hardening: stale legacy `Inbox/control_plane` writers are detected by live container command/bind identity and replaced once with the canonical runtime binding.
- Canonical ReleaseController receives control-plane security migration state after recreate.
- PM version rc55.
