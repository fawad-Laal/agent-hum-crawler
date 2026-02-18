+++
name = "llm-tool-guard"
description = "Prompt injection and suspicious tool-call guard with secret redaction."
events = ["BeforeLLMCall", "AfterLLMCall"]
command = "python ./handler.py"
timeout = 5

[requires]
bins = ["python"]
+++

# LLM Tool Guard

Security hook for:
- `BeforeLLMCall`: redact secrets and block prompt-injection escalation attempts.
- `AfterLLMCall`: block suspicious dangerous tool-call patterns.
