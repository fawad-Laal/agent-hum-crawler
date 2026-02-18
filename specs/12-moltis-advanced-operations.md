# Moltis Advanced Operations

Date: 2026-02-18
Status: Phases A-B completed, Phase C baseline implemented, Phase D pending

## Purpose
Capture additional Moltis-native capabilities to harden operations after MVP sign-off.

## 1. Skill Self-Extension
- Enable controlled runtime skill lifecycle for project-local skills in `.moltis/skills/<name>/SKILL.md`:
  - `create_skill`
  - `update_skill`
  - `delete_skill`
- Governance rules:
  - allow create/update by default for internal workflow acceleration.
  - require explicit human confirmation before `delete_skill`.
  - all skill changes must be logged to an audit artifact.
- Operational check:
  - verify watcher refresh via `skills.changed` behavior in next message.

## 2. Session Branching for Incident Workflows
- Use session forks for incident analysis branches (e.g., alternative severity assumptions).
- Branch naming convention:
  - `incident-<country>-<hazard>-<yyyymmdd>-<purpose>`
- Fork policy:
  - parent session remains canonical reporting chain.
  - forks are exploratory and must be summarized back into parent.

## 3. Hook-Based Policy Enforcement
- Add hooks for:
  - `BeforeLLMCall`: prompt injection and secret redaction checks.
  - `AfterLLMCall`: suspicious tool-call blocking.
  - `BeforeToolCall`: command safety enforcement.
  - `Command`/`MessageSent`: audit logging.
- Hook design constraints:
  - keep timeout <= 5s unless justified.
  - fail-open for observability hooks; fail-closed for high-risk safety hooks.
  - define eligibility requirements (`os`, `bins`, `env`) to avoid noisy failures.

## 4. Production Configuration Profile
- Maintain an explicit hardened `moltis.toml` profile covering:
  - provider/model priorities
  - sandbox mode (`all`) and `no_network` defaults for exec where feasible
  - browser domain restrictions for trusted humanitarian domains
  - hooks registration
  - metrics enabled + Prometheus endpoint
  - memory configuration
- Keep secrets out of `moltis.toml` where possible; prefer provider key store and environment injection.

## 5. Local Validation and E2E Gate
- Adopt Moltis local validation parity flow before release:
  - `./scripts/local-validate.sh`
- Add UI/system test gate strategy:
  - smoke checks for chat send flow, settings persistence, skills refresh, and monitoring dashboards.
  - preserve artifacts on failure for root-cause analysis.

## 6. Implementation Phases (Post-MVP)
1. Phase A: Hook safety baseline + audit logging. Status: Completed.
   Evidence:
   - Active hooks: `ahc-llm-tool-guard`, `ahc-tool-safety-guard`, `ahc-audit-log`.
   - Startup log: `7 hook(s) discovered (4 shell, 3 built-in), 6 registered`.
   - Validation:
     - `BeforeToolCall` blocked `rm -rf /`.
     - `BeforeLLMCall` blocked injection-escalation test.
     - Audit event persisted to `.moltis/logs/hook-audit.jsonl`.
2. Phase B: Hardened `moltis.toml` profile + environment rollout. Status: Completed.
   Evidence:
   - Hardened profile template added at `config/moltis.hardened.example.toml`.
   - Profile includes provider/model priorities, sandbox/network defaults, browser domain restrictions, hooks registration, metrics, and memory settings.
   - Rollout procedure added in `README.md`.
3. Phase C: Skill self-extension governance and branch workflow SOP. Status: Baseline implemented with live branch workflow evidence.
   Evidence:
   - Governance/SOP spec added: `specs/16-phase-c-skill-branch-sop.md`.
   - `delete_skill` safety enforcement added in `src/agent_hum_crawler/hook_policies.py`:
     - requires `confirm=true` and `confirm_phrase="DELETE_SKILL"`.
   - Policy tests added in `tests/test_hook_policies.py`.
   - Live Moltis branch workflow executed on `2026-02-18` via WebSocket RPC:
     - Parent session: `main`
     - Fork RPC: `sessions.fork` with label `incident-madagascar-cyclone-20260218-alt-severity`
     - Child session created: `session:86f57658-2647-4cea-9be7-8f219224f38c`
     - Merge-back summary submitted to parent via `chat.send` after switching back to `main`.
   - Database evidence (`~/.moltis/moltis.db`, `sessions` table):
     - `key=session:86f57658-2647-4cea-9be7-8f219224f38c`
     - `parent_session_key=main`
     - `fork_point=0`
     - `label=incident-madagascar-cyclone-20260218-alt-severity`
4. Phase D: Local-validate and E2E regression gate adoption.

## 7. Acceptance Criteria
- Hook policies block known dangerous tool calls in test scenarios.
- Skill create/update/delete flow works with required approvals and audit trail.
- Branch workflow used in at least one real incident simulation.
- Hardened configuration documented and reproducible.
- Local validation + E2E checks run clean before release branch cut.
