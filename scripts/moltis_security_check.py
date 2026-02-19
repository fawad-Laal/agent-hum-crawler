"""Validate Moltis security/auth baseline and emit evidence artifacts (specs/13)."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

try:
    import tomllib  # py311+
except Exception as exc:  # pragma: no cover
    raise RuntimeError("Python 3.11+ is required for tomllib") from exc


ALLOWED_API_KEY_SCOPES = {
    "operator.read",
    "operator.write",
    "operator.admin",
    "operator.approvals",
    "operator.pairing",
}


def _get(obj: dict, *path: str, default=None):
    cur = obj
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _parse_scopes(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    text = str(raw).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            payload = json.loads(text)
            if isinstance(payload, list):
                return [str(x).strip() for x in payload if str(x).strip()]
        except json.JSONDecodeError:
            pass
    return [s.strip() for s in text.split(",") if s.strip()]


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1",
        (name,),
    )
    return cur.fetchone() is not None


def _fetch_db_evidence(db_path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {
        "db_path": str(db_path),
        "db_exists": db_path.exists(),
        "password_count": 0,
        "passkey_count": 0,
        "active_api_key_count": 0,
        "active_api_keys": [],
    }
    if not db_path.exists():
        return out

    conn = sqlite3.connect(db_path)
    try:
        if _table_exists(conn, "auth_password"):
            out["password_count"] = int(conn.execute("SELECT COUNT(*) FROM auth_password").fetchone()[0])
        if _table_exists(conn, "passkeys"):
            out["passkey_count"] = int(conn.execute("SELECT COUNT(*) FROM passkeys").fetchone()[0])
        if _table_exists(conn, "api_keys"):
            rows = conn.execute(
                """
                SELECT id, label, key_prefix, scopes
                FROM api_keys
                WHERE revoked_at IS NULL
                ORDER BY created_at DESC
                """
            ).fetchall()
            keys: list[dict[str, Any]] = []
            for row in rows:
                key_id, label, key_prefix, scopes_raw = row
                scopes = _parse_scopes(scopes_raw)
                keys.append(
                    {
                        "id": key_id,
                        "label": label,
                        "key_prefix": key_prefix,
                        "scopes": scopes,
                    }
                )
            out["active_api_keys"] = keys
            out["active_api_key_count"] = len(keys)
    finally:
        conn.close()
    return out


def _build_auth_matrix(
    *,
    auth_disabled: bool,
    credentials_configured: bool,
    behind_proxy_env: str,
    expect_behind_proxy: str,
) -> dict[str, Any]:
    proxy_env_bool = str(behind_proxy_env).strip().lower() in {"1", "true", "yes", "on"}
    scenarios: list[dict[str, str]] = []

    # Scenario 1: credentials configured, local access.
    scenarios.append(
        {
            "id": "local_with_credentials",
            "expected": "auth_required",
            "status": "pass" if credentials_configured and not auth_disabled else "fail",
            "evidence": "credentials configured and auth enabled",
        }
    )
    # Scenario 2: credentials configured, remote access.
    scenarios.append(
        {
            "id": "remote_with_credentials",
            "expected": "auth_required",
            "status": "pass" if credentials_configured and not auth_disabled else "fail",
            "evidence": "credentials configured and auth enabled",
        }
    )
    # Scenario 3: no credentials, remote/proxy path should be setup-only.
    if credentials_configured or auth_disabled:
        scenarios.append(
            {
                "id": "remote_no_credentials",
                "expected": "setup_required",
                "status": "pending",
                "evidence": "not applicable because credentials already configured or auth disabled",
            }
        )
    else:
        remote_safe = proxy_env_bool or expect_behind_proxy == "false"
        scenarios.append(
            {
                "id": "remote_no_credentials",
                "expected": "setup_required",
                "status": "pass" if remote_safe else "fail",
                "evidence": (
                    "MOLTIS_BEHIND_PROXY=true present"
                    if proxy_env_bool
                    else "no explicit proxy override; requires header-based remote classification"
                ),
            }
        )
    # Scenario 4: no credentials, local direct loopback convenience.
    if credentials_configured or auth_disabled:
        local_status = "pending"
        local_evidence = "not applicable because credentials already configured or auth disabled"
    else:
        local_status = "pass" if not proxy_env_bool else "pending"
        local_evidence = "available when not behind proxy and no credentials configured"
    scenarios.append(
        {
            "id": "local_no_credentials",
            "expected": "full_access_dev",
            "status": local_status,
            "evidence": local_evidence,
        }
    )

    proxy_expectation_status = "pass"
    proxy_expectation_evidence = "auto mode (no strict proxy expectation)"
    if expect_behind_proxy == "true":
        if proxy_env_bool:
            proxy_expectation_evidence = "MOLTIS_BEHIND_PROXY=true"
        else:
            proxy_expectation_status = "fail"
            proxy_expectation_evidence = "Expected proxy mode, but MOLTIS_BEHIND_PROXY is not true"
    elif expect_behind_proxy == "false":
        if proxy_env_bool:
            proxy_expectation_status = "fail"
            proxy_expectation_evidence = "Expected non-proxy mode, but MOLTIS_BEHIND_PROXY=true is set"
        else:
            proxy_expectation_evidence = "MOLTIS_BEHIND_PROXY not set/false"

    return {
        "status": "pass"
        if all(s["status"] in {"pass", "pending"} for s in scenarios) and proxy_expectation_status == "pass"
        else "fail",
        "behind_proxy_env": behind_proxy_env,
        "expect_behind_proxy": expect_behind_proxy,
        "proxy_expectation_check": {
            "status": proxy_expectation_status,
            "evidence": proxy_expectation_evidence,
        },
        "scenarios": scenarios,
    }


def _build_api_key_checks(
    *,
    active_api_keys: list[dict[str, Any]],
    require_api_keys: bool,
) -> dict[str, Any]:
    unscoped = 0
    invalid_scope_keys: list[dict[str, Any]] = []
    admin_keys = 0
    for key in active_api_keys:
        scopes = [s for s in key.get("scopes", []) if s]
        if not scopes:
            unscoped += 1
        unknown = [s for s in scopes if s not in ALLOWED_API_KEY_SCOPES]
        if unknown:
            invalid_scope_keys.append({"id": key.get("id"), "unknown_scopes": unknown})
        if "operator.admin" in scopes:
            admin_keys += 1

    active_count = len(active_api_keys)
    checks = [
        {
            "id": "active_api_keys_present",
            "expected": ">=1" if require_api_keys else "optional",
            "actual": active_count,
            "status": "pass" if active_count >= 1 or not require_api_keys else "fail",
        },
        {
            "id": "active_api_keys_scoped",
            "expected": "all active keys have >=1 scope",
            "actual": {"active_count": active_count, "unscoped_count": unscoped},
            "status": "pass" if unscoped == 0 else "fail",
        },
        {
            "id": "active_api_keys_scope_values_valid",
            "expected": "all scopes in allowed Moltis operator scope set",
            "actual": invalid_scope_keys,
            "status": "pass" if not invalid_scope_keys else "fail",
        },
        {
            "id": "operator_admin_scope_usage",
            "expected": "minimize operator.admin usage",
            "actual": {"admin_scope_key_count": admin_keys},
            "status": "pass" if admin_keys == 0 else "warning",
        },
    ]
    hard_fail = {"active_api_keys_present", "active_api_keys_scoped", "active_api_keys_scope_values_valid"}
    status = "pass"
    for check in checks:
        if check["id"] in hard_fail and check["status"] != "pass":
            status = "fail"
            break
    return {"status": status, "checks": checks}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Validate Moltis security/auth baseline and output JSON evidence.")
    p.add_argument("--config-path", default=str(Path.home() / ".config" / "moltis" / "moltis.toml"))
    p.add_argument("--db-path", default=str(Path.home() / ".moltis" / "moltis.db"))
    p.add_argument(
        "--expect-behind-proxy",
        choices=["auto", "true", "false"],
        default="auto",
        help="Use true/false to force proxy posture expectation checks; auto keeps it informational.",
    )
    p.add_argument(
        "--require-api-keys",
        action="store_true",
        help="Fail if no active API keys are present.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config_path = Path(args.config_path)
    db_path = Path(args.db_path)
    if not config_path.exists():
        print(json.dumps({"status": "fail", "reason": f"missing config: {config_path}"}, indent=2))
        return 1

    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    db_evidence = _fetch_db_evidence(db_path)
    credentials_configured = (int(db_evidence.get("password_count", 0)) + int(db_evidence.get("passkey_count", 0))) > 0
    behind_proxy_env = os.getenv("MOLTIS_BEHIND_PROXY", "<unset>")

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
    checks.append({"id": "credentials_configured", "expected": ">=1 password or passkey", "actual": credentials_configured})

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
        elif cid == "credentials_configured":
            ok = bool(actual) is True
        else:
            ok = False
        results.append({**c, "status": "pass" if ok else "fail"})

    baseline_hard_fail_ids = {
        "auth_disabled_false",
        "exec_approval_mode_not_never",
        "sandbox_mode_hardened",
        "metrics_enabled",
        "prometheus_enabled",
        "hooks_present",
        "credentials_configured",
    }
    baseline_status = "pass"
    for r in results:
        if r["id"] in baseline_hard_fail_ids and r["status"] != "pass":
            baseline_status = "fail"
            break

    auth_matrix = _build_auth_matrix(
        auth_disabled=bool(_get(payload, "auth", "disabled", default=False)),
        credentials_configured=credentials_configured,
        behind_proxy_env=behind_proxy_env,
        expect_behind_proxy=args.expect_behind_proxy,
    )
    api_key_checks = _build_api_key_checks(
        active_api_keys=list(db_evidence.get("active_api_keys", [])),
        require_api_keys=args.require_api_keys,
    )

    status = "pass" if all(x == "pass" for x in (baseline_status, auth_matrix["status"], api_key_checks["status"])) else "fail"

    out = {
        "status": status,
        "config_path": str(config_path),
        "db_path": str(db_path),
        "baseline_checks": results,
        "auth_matrix": auth_matrix,
        "api_key_scope_verification": api_key_checks,
        "db_observations": db_evidence,
    }
    print(json.dumps(out, indent=2))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
