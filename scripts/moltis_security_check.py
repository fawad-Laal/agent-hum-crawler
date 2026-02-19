"""Validate Moltis security/auth baseline against specs/13."""

from __future__ import annotations

import json
import os
from pathlib import Path

try:
    import tomllib  # py311+
except Exception as exc:  # pragma: no cover
    raise RuntimeError("Python 3.11+ is required for tomllib") from exc


def _get(obj: dict, *path: str, default=None):
    cur = obj
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def main() -> int:
    config_path = Path.home() / ".config" / "moltis" / "moltis.toml"
    if not config_path.exists():
        print(json.dumps({"status": "fail", "reason": f"missing config: {config_path}"}, indent=2))
        return 1

    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))

    checks = []
    checks.append(
        {
            "id": "auth_disabled_false",
            "expected": False,
            "actual": _get(payload, "auth", "disabled", default=False),
        }
    )
    checks.append(
        {
            "id": "exec_approval_mode_not_never",
            "expected": "always|on-miss|smart",
            "actual": _get(payload, "tools", "exec", "approval_mode", default="on-miss"),
        }
    )
    checks.append(
        {
            "id": "sandbox_mode_hardened",
            "expected": "all|non-main",
            "actual": _get(payload, "tools", "exec", "sandbox", "mode", default="off"),
        }
    )
    checks.append(
        {
            "id": "metrics_enabled",
            "expected": True,
            "actual": _get(payload, "metrics", "enabled", default=False),
        }
    )
    checks.append(
        {
            "id": "prometheus_enabled",
            "expected": True,
            "actual": _get(payload, "metrics", "prometheus_endpoint", default=False),
        }
    )
    checks.append(
        {
            "id": "hooks_present",
            "expected": ">=1",
            "actual": len(_get(payload, "hooks", "hooks", default=[])),
        }
    )
    checks.append(
        {
            "id": "behind_proxy_env_set",
            "expected": "true when reverse-proxied",
            "actual": os.getenv("MOLTIS_BEHIND_PROXY", "<unset>"),
        }
    )

    results = []
    for c in checks:
        cid = c["id"]
        actual = c["actual"]
        if cid == "auth_disabled_false":
            ok = actual is False
        elif cid == "exec_approval_mode_not_never":
            ok = str(actual).lower() in {"always", "on-miss", "smart"}
        elif cid == "sandbox_mode_hardened":
            ok = str(actual).lower() in {"all", "non-main"}
        elif cid == "metrics_enabled":
            ok = bool(actual) is True
        elif cid == "prometheus_enabled":
            ok = bool(actual) is True
        elif cid == "hooks_present":
            ok = int(actual) >= 1
        elif cid == "behind_proxy_env_set":
            # informational/pending: only required if actually behind proxy
            ok = str(actual).lower() in {"true", "1", "yes", "on", "<unset>"}
        else:
            ok = False
        results.append({**c, "status": "pass" if ok else "fail"})

    hard_fail_ids = {
        "auth_disabled_false",
        "exec_approval_mode_not_never",
        "sandbox_mode_hardened",
        "metrics_enabled",
        "prometheus_enabled",
        "hooks_present",
    }
    status = "pass"
    for r in results:
        if r["id"] in hard_fail_ids and r["status"] != "pass":
            status = "fail"
            break

    out = {
        "status": status,
        "config_path": str(config_path),
        "checks": results,
    }
    print(json.dumps(out, indent=2))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

