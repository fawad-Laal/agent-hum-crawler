# Moltis Streaming and Tool Registry Alignment

Date: 2026-02-18
Status: Drafted for implementation

## Purpose
Define how this project should align with Moltis streaming internals and tool source management.

## 1. Streaming Event Contract
- Treat streaming as first-class UX for long-running multi-source cycles.
- Align to Moltis stream semantics:
  - `Delta`
  - `ToolCallStart`
  - `ToolCallArgumentsDelta`
  - `ToolCallComplete`
  - `Done`
  - `Error`
- Ensure provider integrations emit terminal `Done` with usage and graceful `Error` handling.

## 2. Runner and Gateway Expectations
- Preserve agent loop behavior:
  1. stream with tools
  2. accumulate tool calls from stream deltas
  3. execute tool calls concurrently
  4. append tool results and continue loop
- Ensure websocket broadcasts remain consistent with UI handlers:
  - `thinking`
  - `thinking_done`
  - `delta`
  - `tool_call_start`
  - `tool_call_end`
  - `iteration`

## 3. Frontend Streaming Performance Guardrails
- Monitor long-response lag from full-markdown re-render on every delta.
- Add operational guardrails for slow clients due to unbounded channels.
- Keep assistant output compact during heavy tool runs to reduce render churn.

## 4. Tool Registry Source-Aware Policy
- Use source metadata from registry schema outputs:
  - builtin tools: `source = "builtin"`
  - MCP tools: `source = "mcp"` + `mcpServer`
- Enforce source-aware controls:
  - allow session-level MCP disable via registry filtering
  - keep critical workflows functional with builtins-only fallback
- Prefer typed source filtering over name-prefix assumptions.

## 5. Validation Checklist
- Streaming path verified end-to-end in chat UI for long runs.
- Tool-call lifecycle visible and ordered in websocket events.
- Session with MCP disabled still operates on builtin toolset.
- Tool schema source metadata visible and correctly grouped by origin.
