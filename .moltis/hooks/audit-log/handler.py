import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        log_file = os.getenv("HOOK_AUDIT_LOG_FILE", ".moltis/logs/hook-audit.jsonl")
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "logged_at": datetime.now(timezone.utc).isoformat(),
            "event": payload.get("event"),
            "session_id": payload.get("session_id"),
            "data": payload.get("data", payload),
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # Fail-open for observability hook.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
