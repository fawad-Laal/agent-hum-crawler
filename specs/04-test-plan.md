# Test Plan - Dynamic Disaster Monitoring Agent

Date: 2026-02-17

## 1. Test Scope
- Input collection and validation
- Monitoring and normalization pipeline
- Severity/confidence assignment
- Deduplication/change detection
- Moltis alert output integrity

## 2. Test Types
- Unit: validation, hashing, severity rules, formatter
- Integration: full cycle with mocked source inputs
- Scenario: multi-country mixed-disaster updates across several cycles
- Failure: provider/source/network partial failures

## 3. Key Test Cases
1. Missing required config input -> clarifying prompt appears.
2. Invalid interval (<5 or >1440) -> rejected with correction hint.
3. Single-source unverified event -> low confidence, not high certainty wording.
4. Repeat event unchanged next cycle -> no duplicate alert.
5. Medium event escalates -> alert emitted as changed update.
6. Critical event during quiet hours -> still emitted.
7. Alert payload missing URL/timestamp -> test fails.

## 4. Acceptance Gates
- Gate A: all required fields validated.
- Gate B: event schema completeness 100%.
- Gate C: duplicate suppression target met.
- Gate D: every emitted alert has source traceability.

## 5. Manual Review Checklist
- Severity and confidence are reasonable for sampled events.
- Facts vs inference language is clear.
- Final output is concise and operational.

## 6. Moltis-Specific Validation
1. Prompt layering check:
- Verify project `AGENTS.md` instructions are applied alongside user persona files from `~/.moltis/`.

2. Streaming behavior:
- During long runs, confirm incremental deltas are visible and tool-call states appear in order.

3. Tool strategy compliance:
- Confirm API/RSS sources are attempted before browser automation in normal cycles.

4. Metrics/tracing coverage:
- Confirm `/metrics` and `/api/metrics` endpoints are available in deployment profile.
- Confirm tool error spikes can be traced to connector/feed failures in app reports.

5. Hook safety tests:
- Validate `BeforeToolCall` blocks dangerous command payload patterns.
- Validate `BeforeLLMCall`/`AfterLLMCall` filtering behavior on prompt-injection fixtures.

6. Skill lifecycle tests:
- Validate `create_skill` and `update_skill` activation on next message.
- Validate `delete_skill` requires explicit user confirmation in workflow policy.

7. Session branching tests:
- Validate forked session inheritance boundaries and independence.
- Validate incident branch labels and summary-back flow.

8. Local validation and e2e checks:
- Record latest local validation run status and relevant e2e artifact paths on failure.

9. Authentication matrix tests:
- Validate tier behavior across: local no-credential, remote setup-required, and credentialed access.
- Validate session cookie, passkey, and scoped API key access paths.

10. Proxy and websocket security tests:
- Validate remote classification and auth enforcement when `MOLTIS_BEHIND_PROXY=true`.
- Validate websocket connect auth for browser session and API-key clients.

11. Third-party skills security tests:
- Validate trust gate (installed/trusted/enabled) and blocked enable for untrusted skills.
- Validate drift auto-untrust behavior and emergency disable procedure.

12. Streaming lifecycle tests:
- Validate `delta`, `tool_call_start`, `tool_call_end`, `thinking`, and `iteration` event order for tool-heavy turns.
- Validate final completion semantics and error-path behavior under provider stream interruptions.

13. Tool registry source tests:
- Validate schema output includes `source` and MCP server metadata.
- Validate MCP-disable mode removes MCP tools while builtin tools remain available.
