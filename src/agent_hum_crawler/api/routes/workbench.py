"""Report Workbench routes — POST /api/report-workbench, profile CRUD.

The workbench runs two report passes (deterministic + AI) and returns
both side-by-side.  Like all long-running ops it returns 202 + job_id.
Profiles are stored in ``config/dashboard_workbench_profiles.json``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent_hum_crawler.api.job_store import JOB_STORE

router = APIRouter()

_ROOT = Path(__file__).resolve().parents[5]
_PROFILE_FILE = _ROOT / "config" / "dashboard_workbench_profiles.json"
_REPORTS_DIR = _ROOT / "reports"


# ── profile helpers ───────────────────────────────────────────────────────


def _default_profile() -> dict[str, Any]:
    try:
        from agent_hum_crawler.feature_flags import load_feature_flags
        flags = load_feature_flags()
    except Exception:
        flags = {}
    return {
        "countries": "Madagascar,Mozambique",
        "disaster_types": "cyclone/storm,flood",
        "max_age_days": int(flags.get("max_item_age_days_default", 30) or 30),
        "limit_cycles": 20,
        "limit_events": 30,
        "report_template": "config/report_template.brief.json",
        "country_min_events": 1,
        "max_per_connector": 8,
        "max_per_source": 4,
    }


def _normalize(src: dict | None) -> dict[str, Any]:
    base = _default_profile()
    if not src:
        return base
    base["countries"] = str(src.get("countries", base["countries"]))
    base["disaster_types"] = str(src.get("disaster_types", base["disaster_types"]))
    for k in ("limit_cycles", "limit_events", "max_age_days", "country_min_events",
              "max_per_connector", "max_per_source"):
        try:
            base[k] = int(src.get(k, base[k]))
        except Exception:
            pass
    base["limit_cycles"] = max(1, min(base["limit_cycles"], 200))
    base["limit_events"] = max(1, min(base["limit_events"], 500))
    base["max_age_days"] = max(1, min(base["max_age_days"], 3650))
    base["country_min_events"] = max(0, base["country_min_events"])
    tpl = str(src.get("report_template", base["report_template"]))
    if tpl.startswith("config/") and tpl.endswith(".json"):
        base["report_template"] = tpl
    return base


def _load_store() -> dict[str, Any]:
    if not _PROFILE_FILE.exists():
        return {"presets": {}, "last_profile": _default_profile()}
    try:
        payload = json.loads(_PROFILE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"presets": {}, "last_profile": _default_profile()}
    presets = {
        str(k).strip(): _normalize(v if isinstance(v, dict) else {})
        for k, v in payload.get("presets", {}).items()
        if str(k).strip()
    }
    return {"presets": presets, "last_profile": _normalize(payload.get("last_profile"))}


def _save_store(store: dict) -> None:
    _PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PROFILE_FILE.write_text(json.dumps(store, indent=2), encoding="utf-8")


# ── report-building worker ────────────────────────────────────────────────


def _section_word_usage(markdown: str, section_titles: list[str]) -> dict[str, int]:
    lines = markdown.splitlines()
    sections: dict[str, list[str]] = {t: [] for t in section_titles}
    current: str | None = None
    title_map = {f"## {t}": t for t in section_titles}
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            current = title_map.get(stripped)
            continue
        if current:
            sections[current].append(line)
    return {t: len(re.findall(r"\b[\w/-]+\b", "\n".join(lines))) for t, lines in sections.items()}


def _build_one_report(profile: dict, *, use_llm: bool) -> dict[str, Any]:
    """Build a single report pass, returning payload + markdown."""
    from agent_hum_crawler.feature_flags import get_feature_flag
    from agent_hum_crawler.reporting import (
        build_graph_context,
        evaluate_report_quality,
        load_report_template,
        render_long_form_report,
        write_report_file,
    )
    from agent_hum_crawler.settings import load_environment

    load_environment()

    template_path = Path(profile["report_template"])
    template = load_report_template(template_path)
    sections = template.get("sections", {})
    required_sections = [
        str(sections.get("executive_summary", "Executive Summary")),
        str(sections.get("incident_highlights", "Incident Highlights")),
        str(sections.get("source_reliability", "Source and Connector Reliability Snapshot")),
        str(sections.get("risk_outlook", "Risk Outlook")),
        str(sections.get("method", "Method")),
    ]

    countries = [c.strip() for c in profile["countries"].split(",") if c.strip()]
    disaster_types = [d.strip() for d in profile["disaster_types"].split(",") if d.strip()]
    strict_filters = bool(get_feature_flag("report_strict_filters_default", True))

    graph_context = build_graph_context(
        countries=countries,
        disaster_types=disaster_types,
        limit_cycles=profile["limit_cycles"],
        limit_events=profile["limit_events"],
        strict_filters=strict_filters,
        max_age_days=profile["max_age_days"],
        country_min_events=profile["country_min_events"],
        max_per_connector=profile["max_per_connector"],
        max_per_source=profile["max_per_source"],
    )
    markdown = render_long_form_report(
        graph_context=graph_context,
        title="Disaster Intelligence Report",
        use_llm=use_llm,
        template_path=template_path,
    )
    quality = evaluate_report_quality(report_markdown=markdown, required_sections=required_sections)
    out = write_report_file(report_markdown=markdown)

    return {
        "status": "ok",
        "report_path": str(out),
        "meta": graph_context.get("meta", {}),
        "llm_used": use_llm,
        "report_quality": quality,
        "markdown": markdown,
    }


def _do_workbench(profile: dict) -> dict[str, Any]:
    from agent_hum_crawler.database import init_db
    init_db()

    template_path = Path(profile["report_template"])
    try:
        tpl = json.loads((Path(_ROOT) / template_path).read_text(encoding="utf-8"))
    except Exception:
        tpl = {}
    section_map = tpl.get("sections", {}) if isinstance(tpl.get("sections"), dict) else {}
    limits = tpl.get("limits", {}) if isinstance(tpl.get("limits"), dict) else {}
    section_titles = [
        str(section_map.get("executive_summary", "Executive Summary")),
        str(section_map.get("incident_highlights", "Incident Highlights")),
        str(section_map.get("source_reliability", "Source and Connector Reliability Snapshot")),
        str(section_map.get("risk_outlook", "Risk Outlook")),
        str(section_map.get("method", "Method")),
    ]

    det = _build_one_report(profile, use_llm=False)
    ai = _build_one_report(profile, use_llm=True)

    return {
        "profile": profile,
        "template": {"path": str(template_path), "sections": section_map, "limits": limits},
        "deterministic": {
            **det,
            "section_word_usage": _section_word_usage(det.get("markdown", ""), section_titles),
        },
        "ai": {
            **ai,
            "section_word_usage": _section_word_usage(ai.get("markdown", ""), section_titles),
        },
    }


# ── Request models ────────────────────────────────────────────────────────


class ProfileSaveRequest(BaseModel):
    name: str
    profile: dict[str, Any] = {}


class ProfileDeleteRequest(BaseModel):
    name: str


# ── Routes ────────────────────────────────────────────────────────────────


@router.get("/workbench-profiles")
def get_profiles() -> dict:
    return _load_store()


@router.post("/report-workbench", status_code=202)
def run_workbench(body: dict) -> dict:
    profile = _normalize(body)
    store = _load_store()
    store["last_profile"] = profile
    _save_store(store)
    job_id = JOB_STORE.submit(lambda _p=profile: _do_workbench(_p))
    return {"job_id": job_id, "status": "queued"}


@router.post("/report-workbench/rerun-last", status_code=202)
def rerun_last_workbench() -> dict:
    store = _load_store()
    profile = _normalize(store.get("last_profile"))
    store["last_profile"] = profile
    _save_store(store)
    job_id = JOB_STORE.submit(lambda _p=profile: _do_workbench(_p))
    return {"job_id": job_id, "status": "queued"}


@router.post("/workbench-profiles/save")
def save_profile(body: ProfileSaveRequest) -> dict:
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Preset name is required")
    profile = _normalize(body.profile)
    store = _load_store()
    store["presets"][name] = profile
    store["last_profile"] = profile
    _save_store(store)
    return {"status": "ok", "store": store}


@router.post("/workbench-profiles/delete")
def delete_profile(body: ProfileDeleteRequest) -> dict:
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Preset name is required")
    store = _load_store()
    store["presets"].pop(name, None)
    _save_store(store)
    return {"status": "ok", "store": store}
