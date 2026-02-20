"""Environment and runtime settings."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from .feature_flags import get_feature_flag


def load_environment() -> None:
    load_dotenv(override=False)


def is_reliefweb_enabled() -> bool:
    return bool(get_feature_flag("reliefweb_enabled", True))


def get_reliefweb_appname() -> str:
    appname = os.getenv("RELIEFWEB_APPNAME", "").strip()
    if not appname:
        raise RuntimeError(
            "RELIEFWEB_APPNAME is required. Register one at "
            "https://apidoc.reliefweb.int/parameters#appname"
        )
    return appname


def is_llm_enrichment_enabled() -> bool:
    return bool(get_feature_flag("llm_enrichment_enabled", False))


def get_openai_api_key() -> str:
    return os.getenv("OPENAI_API_KEY", "").strip()


def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
