+++
name = "tool-safety-guard"
description = "Blocks dangerous command patterns before tool execution."
events = ["BeforeToolCall"]
command = "python ./handler.py"
timeout = 5

[requires]
bins = ["python"]
+++

# Tool Safety Guard

Fail-closed safety guard for `BeforeToolCall`:
- blocks high-risk destructive shell command patterns.
