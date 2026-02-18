import json
import sys
from pathlib import Path


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in [here.parent, *here.parents]:
        if (candidate / "src" / "agent_hum_crawler").exists():
            return candidate
    return here.parents[4]


ROOT = _repo_root()
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from agent_hum_crawler.hook_policies import (  # noqa: E402
    redact_secrets,
    should_block_after_llm,
    should_block_before_llm,
)


def main() -> int:
    payload = json.load(sys.stdin)
    event = payload.get("event", "")
    data = payload.get("data", payload)

    if event == "BeforeLLMCall":
        reason = should_block_before_llm(data)
        if reason:
            print(reason, file=sys.stderr)
            return 1
        redacted, changed = redact_secrets(data)
        if changed:
            print(json.dumps({"action": "modify", "data": redacted}))
    elif event == "AfterLLMCall":
        reason = should_block_after_llm(data)
        if reason:
            print(reason, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
