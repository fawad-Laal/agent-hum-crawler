import json
import sqlite3
import subprocess
import sys
from pathlib import Path


def _write_config(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "[auth]",
                "disabled = false",
                "",
                "[tools.exec]",
                'approval_mode = "on-miss"',
                "",
                "[tools.exec.sandbox]",
                'mode = "all"',
                "",
                "[metrics]",
                "enabled = true",
                "prometheus_endpoint = true",
                "",
                "[hooks]",
                "[[hooks.hooks]]",
                'name = "audit"',
                'command = "./hooks/audit.sh"',
                'events = ["BeforeToolCall"]',
                "timeout = 5",
            ]
        ),
        encoding="utf-8",
    )


def _init_db(path: Path, *, api_key_scopes: str | None = None) -> None:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE auth_password (id INTEGER PRIMARY KEY, password_hash TEXT)")
    cur.execute("CREATE TABLE passkeys (id TEXT PRIMARY KEY, passkey_data TEXT)")
    cur.execute(
        """
        CREATE TABLE api_keys (
            id TEXT PRIMARY KEY,
            label TEXT,
            key_hash TEXT,
            key_prefix TEXT,
            created_at TEXT,
            revoked_at TEXT,
            scopes TEXT
        )
        """
    )
    cur.execute("INSERT INTO auth_password (password_hash) VALUES ('hash')")
    if api_key_scopes is not None:
        cur.execute(
            """
            INSERT INTO api_keys (id, label, key_hash, key_prefix, created_at, revoked_at, scopes)
            VALUES ('k1', 'test', 'hash', 'mk_abc', '2026-02-18T00:00:00Z', NULL, ?)
            """,
            (api_key_scopes,),
        )
    conn.commit()
    conn.close()


def _run_check(config_path: Path, db_path: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/moltis_security_check.py",
            "--config-path",
            str(config_path),
            "--db-path",
            str(db_path),
            *extra_args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_security_check_passes_with_scoped_api_key(tmp_path: Path) -> None:
    config_path = tmp_path / "moltis.toml"
    db_path = tmp_path / "moltis.db"
    _write_config(config_path)
    _init_db(db_path, api_key_scopes='["operator.read","operator.write"]')

    proc = _run_check(config_path, db_path, "--require-api-keys")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["status"] == "pass"
    assert payload["api_key_scope_verification"]["status"] == "pass"
    assert payload["auth_matrix"]["status"] == "pass"


def test_security_check_fails_for_unscoped_api_key(tmp_path: Path) -> None:
    config_path = tmp_path / "moltis.toml"
    db_path = tmp_path / "moltis.db"
    _write_config(config_path)
    _init_db(db_path, api_key_scopes="")

    proc = _run_check(config_path, db_path, "--require-api-keys")
    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload["status"] == "fail"
    assert payload["api_key_scope_verification"]["status"] == "fail"


def test_security_check_fails_when_proxy_expected_but_unset(tmp_path: Path) -> None:
    config_path = tmp_path / "moltis.toml"
    db_path = tmp_path / "moltis.db"
    _write_config(config_path)
    _init_db(db_path, api_key_scopes='["operator.read"]')

    proc = _run_check(config_path, db_path, "--expect-behind-proxy", "true")
    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload["status"] == "fail"
    assert payload["auth_matrix"]["proxy_expectation_check"]["status"] == "fail"
