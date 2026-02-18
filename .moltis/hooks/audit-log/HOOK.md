+++
name = "audit-log"
description = "Fail-open audit logging for command, message, and tool lifecycle events."
events = ["Command", "MessageSent", "AfterToolCall", "BeforeToolCall", "AfterLLMCall"]
command = "python ./handler.py"
timeout = 5

[requires]
bins = ["python"]
+++

# Audit Log

Fail-open observability hook that appends event payloads to JSONL.
Default output file:
- `./.moltis/logs/hook-audit.jsonl`
