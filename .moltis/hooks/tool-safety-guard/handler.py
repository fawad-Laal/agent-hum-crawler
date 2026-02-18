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

from agent_hum_crawler.hook_policies import should_block_tool_call  # noqa: E402


def main() -> int:
    payload = json.load(sys.stdin)
    data = payload.get("data", payload)
    tool = str(data.get("tool", ""))
    arguments = data.get("arguments", {}) if isinstance(data.get("arguments", {}), dict) else {}
    reason = should_block_tool_call(tool, arguments)
    if reason:
        print(reason, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
