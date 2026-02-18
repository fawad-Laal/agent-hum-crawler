# Moltis Security and Authentication Profile

Date: 2026-02-18
Status: Drafted for implementation

## Purpose
Define deployment-grade authentication and security controls for this assistant when running in Moltis.

## 1. Unified Auth Gate Policy
- Treat Moltis `check_auth()` behavior as the single source of truth for access decisions.
- Operate with three-tier semantics:
  1. full auth when credentials exist
  2. local-dev convenience only when no credentials and direct loopback
  3. onboarding-only for remote/proxied access when setup incomplete
- Production rule: credentials must be configured; do not rely on tier-2 local bypass.

## 2. Credential and Access Model
- Supported auth mechanisms:
  - password sessions
  - passkeys (WebAuthn)
  - API keys (scoped)
- API key scope policy:
  - monitoring integrations: `operator.read`
  - automation agents: `operator.read,operator.write`
  - approvals workflow: add `operator.approvals`
  - avoid `operator.admin` unless explicitly required
- Enforce least privilege and key rotation SOP.

## 3. Reverse Proxy and Remote Access Safety
- If running behind reverse proxy, set `MOLTIS_BEHIND_PROXY=true` unless proxy headers are verified safe.
- Ensure proxy forwards `Host` and `Origin` correctly for WebSocket protections.
- Treat internet-facing traffic as remote regardless of loopback bind.
- Keep TLS termination at edge proxy and keep private upstream network path.

## 4. Endpoint Throttling and Abuse Controls
- Keep Moltis built-in endpoint throttling enabled.
- Add edge throttling/WAF controls for internet exposure.
- Monitor and alert on repeated auth failures and websocket upgrade bursts.

## 5. Command and Sandbox Security Defaults
- Maintain human-in-the-loop approvals (`approval_mode = smart` minimum).
- Keep sandbox enabled for command execution in production flows.
- Apply resource limits for sandbox commands to reduce blast radius.

## 6. Third-Party Skills Security
- Apply trust lifecycle for external skills/plugins:
  - installed -> trusted -> enabled
- Enforce provenance pinning and drift re-trust requirements.
- Require explicit confirmation for dependency installs and block risky install chains by default.
- Keep emergency disable procedure documented and tested.
- Monitor `~/.moltis/logs/security-audit.jsonl` for skill/plugin security events.

## 7. Required Configuration Baseline
- `auth.disabled = false`
- scoped API keys only
- sandbox mode enabled for exec
- hooks active for LLM/tool safety filtering
- metrics enabled for security observability
- reverse-proxy hardening variables documented

## 8. Verification Checklist
- Auth behavior validated for local, remote, and proxied scenarios.
- API keys validated by scope (allow and deny cases).
- WebSocket auth validated for session-cookie and API-key handshake paths.
- Proxy deployment validated with `MOLTIS_BEHIND_PROXY=true`.
- Third-party skill trust/drift controls validated in test environment.
