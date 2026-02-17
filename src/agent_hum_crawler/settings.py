"""Environment and runtime settings."""

from __future__ import annotations

import os

from dotenv import load_dotenv


def load_environment() -> None:
    load_dotenv(override=False)


def is_reliefweb_enabled() -> bool:
    raw = os.getenv("RELIEFWEB_ENABLED", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def get_reliefweb_appname() -> str:
    appname = os.getenv("RELIEFWEB_APPNAME", "").strip()
    if not appname:
        raise RuntimeError(
            "RELIEFWEB_APPNAME is required. Register one at "
            "https://apidoc.reliefweb.int/parameters#appname"
        )
    return appname
