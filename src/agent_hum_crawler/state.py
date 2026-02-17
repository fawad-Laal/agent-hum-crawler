"""State persistence for monitoring cycles."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


@dataclass
class RuntimeState:
    last_cycle_hashes: List[str] = field(default_factory=list)
    last_run_at: Optional[str] = None
    last_summary: str = ""

    def touch(self) -> None:
        self.last_run_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "last_cycle_hashes": self.last_cycle_hashes,
            "last_run_at": self.last_run_at,
            "last_summary": self.last_summary,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "RuntimeState":
        return cls(
            last_cycle_hashes=list(payload.get("last_cycle_hashes", [])),
            last_run_at=payload.get("last_run_at"),
            last_summary=payload.get("last_summary", ""),
        )


def default_state_path() -> Path:
    return Path.home() / ".moltis" / "agent-hum-crawler" / "runtime_state.json"


def load_state(path: Optional[Path] = None) -> RuntimeState:
    state_path = path or default_state_path()
    if not state_path.exists():
        return RuntimeState()
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    return RuntimeState.from_dict(payload)


def save_state(state: RuntimeState, path: Optional[Path] = None) -> Path:
    state_path = path or default_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
    return state_path
