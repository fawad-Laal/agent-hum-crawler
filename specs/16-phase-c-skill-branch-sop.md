# Phase C - Skill Governance and Session Branching SOP

Date: 2026-02-18
Status: Baseline implemented (governance enforcement + SOP), incident simulation pending

## Purpose
Define safe operating rules for runtime skill lifecycle (`create_skill`, `update_skill`, `delete_skill`) and incident-analysis session branching.

## 1. Skill Lifecycle Governance

### Policy Matrix
- `create_skill`: allowed by default; must be auditable.
- `update_skill`: allowed by default; must be auditable.
- `delete_skill`: blocked unless explicit human confirmation is present.

### Enforced Delete Confirmation
`delete_skill` is allowed only when both are included in tool arguments:
- `confirm = true`
- `confirm_phrase = "DELETE_SKILL"`

If either is missing, the safety hook blocks execution.

### Audit Requirements
All skill lifecycle operations must be logged through hook audit output:
- `.moltis/logs/hook-audit.jsonl`

Minimum fields expected per entry:
- `logged_at`
- `event`
- `session_id`
- `data`

## 2. Session Branching SOP (Incident Workflow)

### When to Branch
Create a branch session when:
- exploring alternative severity/confidence assumptions,
- testing contradictory source interpretations,
- trialing different escalation recommendations.

### Branch Label Standard
Use:
- `incident-<country>-<hazard>-<yyyymmdd>-<purpose>`

Example:
- `incident-madagascar-cyclone-20260218-alt-severity`

### Branch Procedure
1. Fork from current incident session at latest stable message.
2. Set branch label using naming standard.
3. Run exploratory analysis in branch only.
4. Produce a merge-back summary in parent session with:
   - what changed,
   - why,
   - what evidence supports the selected conclusion,
   - links/citations used.

### Parent/Child Rule
- Parent session remains canonical reporting chain.
- Child session is exploratory only.

## 3. Operator Runbook Snippets

### Skill Delete (approved path)
Tool args contract:
```json
{
  "name": "example-skill",
  "confirm": true,
  "confirm_phrase": "DELETE_SKILL"
}
```

### Branch Session
Tool args contract:
```json
{
  "at_message": 12,
  "label": "incident-mozambique-flood-20260218-alt-corroboration"
}
```

## 4. Acceptance Criteria (Phase C)
- `delete_skill` is blocked without explicit confirmation fields.
- Skill operations are visible in audit log output.
- At least one incident branch follows naming standard and merge-back summary pattern.

