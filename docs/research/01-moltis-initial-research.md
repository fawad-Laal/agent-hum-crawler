# Moltis Personal Assistant - Initial Research

Date: 2026-02-17
Project root: `c:\Users\Hussain\Fawad-Software-Projects\Personal-Assistant-Moltis`

## Sources reviewed
- https://moltis.org/
- https://docs.moltis.org/
- https://docs.moltis.org/getting-started/installation
- https://docs.moltis.org/getting-started/introduction
- https://github.com/moltis-org/moltis

## What Moltis is
Moltis is a local-first AI automation framework for building agents that run on your own machine. It supports local and cloud LLM providers and emphasizes safe execution through sandboxed shell usage, permission controls, and network restrictions.

## Quick architecture notes (from docs)
- **Profiles**: named assistant configurations (model, provider, behavior, permissions).
- **Actions**: reusable commands/tasks for workflows.
- **Memory**: local and optional shared memory layers.
- **Watch directories**: trigger automations from file changes.
- **Permission modes**: tune how much autonomy assistants get before asking.

## Install attempts in this environment
Requested command:

```bash
curl -fsSL https://www.moltis.org/install.sh | sh
```

Result on this machine:
- Failed because `sh` is not installed in this PowerShell environment.

Tried docs Windows command:

```powershell
iwr https://moltis.org/install.ps1 -useb | iex
```

Result on 2026-02-17:
- `404 Not Found` from `https://moltis.org/install.ps1` (same with `www.moltis.org`).

## Practical setup path now
1. Install Moltis via a shell that has `sh` (Git Bash, WSL, or MSYS2), then rerun:
   - `curl -fsSL https://www.moltis.org/install.sh | sh`
2. Or check latest release binaries directly in GitHub Releases if installer endpoints are temporarily broken.
3. After successful install, verify:
   - `moltis --version`
4. Initialize your assistant project config (profiles + permissions + provider keys) and keep configs under `docs/research` while iterating.

## Personal assistant project kickoff checklist
- Define assistant scope:
  - calendar/task management
  - note capture/summarization
  - file organization
  - code helper tasks
- Choose provider strategy:
  - local-first model for privacy-sensitive tasks
  - cloud fallback for heavy reasoning
- Define safety profile:
  - default read-only shell and explicit approval for write/network-sensitive steps
- Build first three automations:
  - inbox triage
  - daily summary
  - project note sync

## Next research docs to add
- `docs/research/02-assistant-scope.md`
- `docs/research/03-provider-and-model-choice.md`
- `docs/research/04-safety-and-permissions.md`
- `docs/research/05-first-automations.md`
