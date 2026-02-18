"""Shared policy logic for Moltis hook handlers."""

from __future__ import annotations

import copy
import re
from typing import Any


PROMPT_INJECTION_RE = re.compile(
    r"(ignore\s+previous|disregard\s+previous|new\s+instructions|reveal\s+system\s+prompt|developer\s+message)",
    re.IGNORECASE,
)
TOOL_ESCALATION_RE = re.compile(
    r"(exec|bash|shell|powershell|command|tool)",
    re.IGNORECASE,
)

SECRET_PATTERNS = [
    (re.compile(r"sk-[a-zA-Z0-9_\-]{20,}"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"ghp_[a-zA-Z0-9]{20,}"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"(api[_-]?key\s*[=:]\s*)[^\s\"']+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(password\s*[=:]\s*)[^\s\"']+", re.IGNORECASE), r"\1[REDACTED]"),
]


def detect_prompt_injection(text: str) -> bool:
    return bool(PROMPT_INJECTION_RE.search(text or ""))


def detect_tool_escalation(text: str) -> bool:
    return bool(TOOL_ESCALATION_RE.search(text or ""))


def redact_secrets(value: Any) -> tuple[Any, bool]:
    changed = False

    def _walk(node: Any) -> Any:
        nonlocal changed
        if isinstance(node, str):
            output = node
            for pattern, replacement in SECRET_PATTERNS:
                redacted = pattern.sub(replacement, output)
                if redacted != output:
                    changed = True
                output = redacted
            return output
        if isinstance(node, list):
            return [_walk(x) for x in node]
        if isinstance(node, dict):
            sanitized: dict[Any, Any] = {}
            for k, v in node.items():
                key = str(k).lower()
                if key in {"password", "api_key", "apikey", "token", "secret"} and isinstance(v, str):
                    changed = True
                    sanitized[k] = "[REDACTED]"
                else:
                    sanitized[k] = _walk(v)
            return sanitized
        return node

    return _walk(copy.deepcopy(value)), changed


def collect_message_text(payload_data: dict[str, Any]) -> str:
    messages = payload_data.get("messages", []) or []
    parts: list[str] = []
    for msg in messages:
        if isinstance(msg, dict):
            content = msg.get("content")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        text = block.get("text")
                        if isinstance(text, str):
                            parts.append(text)
    return "\n".join(parts)


def should_block_before_llm(payload_data: dict[str, Any]) -> str | None:
    text = collect_message_text(payload_data)
    if detect_prompt_injection(text) and detect_tool_escalation(text):
        return "Blocked suspected prompt injection with tool escalation intent before LLM call."
    return None


def should_block_after_llm(payload_data: dict[str, Any]) -> str | None:
    text = str(payload_data.get("text") or "")
    tool_calls = payload_data.get("tool_calls", []) or []
    names: list[str] = []
    for call in tool_calls:
        if isinstance(call, dict):
            maybe = call.get("name")
            if isinstance(maybe, str):
                names.append(maybe.lower())
    dangerous = any(name in {"exec", "bash", "shell", "powershell", "shell_command"} for name in names)
    if dangerous and detect_prompt_injection(text):
        return "Blocked suspicious dangerous tool-call request after LLM response."
    return None


def should_block_tool_call(tool: str, arguments: dict[str, Any]) -> str | None:
    name = (tool or "").lower()
    command = str(arguments.get("command", "") or "")
    haystack = f"{name} {command}".lower()

    if name == "delete_skill":
        confirm = bool(arguments.get("confirm"))
        confirm_phrase = str(arguments.get("confirm_phrase", "") or "").strip().upper()
        if not confirm or confirm_phrase != "DELETE_SKILL":
            return (
                "Blocked delete_skill: explicit confirmation required "
                "(confirm=true and confirm_phrase='DELETE_SKILL')."
            )

    blocked_patterns = [
        r"rm\s+-rf\s+/",
        r"del\s+/s\s+/q\s+c:\\",
        r"format\s+c:",
        r"shutdown\s+",
        r"reboot\s+",
        r"curl.+\|\s*(sh|bash)",
        r"invoke-webrequest.+\|\s*iex",
    ]
    for pat in blocked_patterns:
        if re.search(pat, haystack):
            return f"Blocked dangerous command pattern: {pat}"
    return None
