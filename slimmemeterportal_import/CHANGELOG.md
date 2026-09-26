## 32.5.22
- Type-2 control-plane runtime binding hardening: stale legacy `Inbox/control_plane` writers are detected by live container command/bind identity and replaced once with the canonical runtime binding.
- Canonical ReleaseController receives control-plane security migration state after recreate.
- PM version rc55.

## 32.5.21
- Type-2 live-continuation fix for shared ReleaseController destination merges and privileged filesystem validation.
- PM version rc54.
