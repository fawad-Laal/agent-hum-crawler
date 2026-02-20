"""Pipeline Coordinator — single source of truth for the Moltis pipeline.

Resolves coordination gaps identified in the cross-module audit:
  G2 – SA hardcodes strict_filters=True; coordinator exposes all params.
  G3 – SA ignores balancing params (country_min_events, etc.).
  G4 – Independent build_graph_context calls; coordinator caches evidence.
  G5 – Ontology rebuilt from scratch on every SA call; coordinator caches it.
  G8/R3 – DB engine rebuilt each call; coordinator holds a shared engine.
  G7 – Duplicate utility functions; coordinator routes through llm_utils.

Pipeline stages (Phase 4):

  1. **Evidence**   – gather evidence from DB (build_graph_context)
  2. **Ontology**   – build HumanitarianOntologyGraph with multi-impact
  3. **Report**     – render long-form Markdown report
  4. **SA**         – render OCHA Situation Analysis
  5. **Persist**    – (optional) persist ontology to DB
  6. **Write**      – write report + SA files to disk

Each stage is wrapped by ``_run_stage()`` for uniform error capture,
timing, and optional progress callbacks.

Usage
-----
>>> coord = PipelineCoordinator(countries=["madagascar"])
>>> ctx = coord.gather_evidence()
>>> onto = coord.build_ontology()
>>> report = coord.render_report(title="Test")
>>> sa = coord.render_situation_analysis(event_name="Cyclone Freddy")
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Callable

_log = logging.getLogger(__name__)

# Type alias for progress callbacks: (stage_name, status, detail_dict)
ProgressCallback = Callable[[str, str, dict[str, Any]], None]


# ── Pipeline Context (shared state object) ───────────────────────────


@dataclass
class PipelineContext:
    """Immutable snapshot of one pipeline run's state.

    Populated by the coordinator as each stage completes.
    """

    # Evidence stage
    graph_context: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    # Ontology stage
    ontology: Any | None = None  # HumanitarianOntologyGraph

    # Outputs
    report_md: str = ""
    sa_md: str = ""
    report_quality: dict[str, Any] = field(default_factory=dict)
    report_path: Path | None = None
    sa_path: Path | None = None

    # Timing
    started_at: str = ""
    evidence_at: str = ""
    ontology_at: str = ""
    report_at: str = ""
    sa_at: str = ""
    finished_at: str = ""

    # Phase 4: stage-level diagnostics & error aggregation
    stage_errors: dict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list),
    )
    stage_diagnostics: dict[str, dict[str, Any]] = field(
        default_factory=dict,
    )

    @property
    def has_errors(self) -> bool:
        return any(bool(v) for v in self.stage_errors.values())

    @property
    def total_errors(self) -> int:
        return sum(len(v) for v in self.stage_errors.values())


# ── Coordinator ──────────────────────────────────────────────────────


class PipelineCoordinator:
    """Central coordinator for the Moltis evidence → ontology → report pipeline.

    Manages a single DB engine, a single evidence-gathering pass, and a
    cached ontology.  Both report and SA rendering draw from the same
    underlying data, eliminating redundant queries and stale-data drift.

    Parameters
    ----------
    countries :
        Country filter list (e.g. ``["madagascar"]``).
    disaster_types :
        Disaster-type filter list (e.g. ``["cyclone"]``).
    limit_cycles :
        Max recent cycles to consider.
    limit_events :
        Max evidence events after balancing.
    max_age_days :
        Only include events published within N days.
    strict_filters :
        If True, omit events that don't match filters exactly.
    country_min_events :
        Minimum events per country in balanced selection.
    max_per_connector :
        Cap per connector in balanced selection.
    max_per_source :
        Cap per source type in balanced selection.
    db_path :
        Override DB location (mostly for tests).
    on_progress :
        Optional callback ``(stage, status, details)`` for live progress.
    """

    def __init__(
        self,
        *,
        countries: list[str] | None = None,
        disaster_types: list[str] | None = None,
        limit_cycles: int = 20,
        limit_events: int = 80,
        max_age_days: int | None = None,
        strict_filters: bool = True,
        country_min_events: int = 0,
        max_per_connector: int = 0,
        max_per_source: int = 0,
        db_path: Path | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        self.countries = countries
        self.disaster_types = disaster_types
        self.limit_cycles = limit_cycles
        self.limit_events = limit_events
        self.max_age_days = max_age_days
        self.strict_filters = strict_filters
        self.country_min_events = country_min_events
        self.max_per_connector = max_per_connector
        self.max_per_source = max_per_source
        self.db_path = db_path
        self._on_progress = on_progress

        # Shared engine — created lazily
        self._engine: Any | None = None

        # Pipeline state
        self._ctx = PipelineContext(started_at=datetime.now(UTC).isoformat())

    # ── Engine management ────────────────────────────────────────────

    @property
    def engine(self) -> Any:
        """Lazily create and return the shared DB engine."""
        if self._engine is None:
            from .database import build_engine

            self._engine = build_engine(self.db_path)
            _log.debug("Coordinator: shared DB engine created at %s", self.db_path)
        return self._engine

    # ── Context access ───────────────────────────────────────────────

    @property
    def ctx(self) -> PipelineContext:
        """Access the pipeline context snapshot."""
        return self._ctx

    # ── Stage execution wrapper ──────────────────────────────────────

    def _run_stage(
        self,
        stage_name: str,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute *fn* inside a stage wrapper that captures errors, timing,
        and fires the progress callback."""
        self._notify(stage_name, "started", {})
        start = time.monotonic()
        try:
            result = fn(*args, **kwargs)
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)
            self._ctx.stage_diagnostics[stage_name] = {
                "status": "ok",
                "elapsed_ms": elapsed_ms,
            }
            self._notify(stage_name, "completed", {"elapsed_ms": elapsed_ms})
            return result
        except Exception as exc:
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)
            error_msg = f"{type(exc).__name__}: {exc}"
            self._ctx.stage_errors[stage_name].append(error_msg)
            self._ctx.stage_diagnostics[stage_name] = {
                "status": "error",
                "elapsed_ms": elapsed_ms,
                "error": error_msg,
            }
            self._notify(stage_name, "error", {"error": error_msg, "elapsed_ms": elapsed_ms})
            _log.error("Coordinator: stage %s failed: %s", stage_name, error_msg)
            raise

    def _notify(self, stage: str, status: str, details: dict[str, Any]) -> None:
        """Fire the progress callback if registered."""
        if self._on_progress is not None:
            try:
                self._on_progress(stage, status, details)
            except Exception:
                _log.debug("Progress callback error for stage %s", stage, exc_info=True)

    # ── Stage 1: Evidence Gathering ──────────────────────────────────

    def gather_evidence(self, *, force: bool = False) -> dict[str, Any]:
        """Run ``build_graph_context`` with all configured params.

        Returns the full graph_context dict.  Result is cached; pass
        ``force=True`` to re-query.
        """
        if self._ctx.evidence and not force:
            _log.debug("Coordinator: returning cached evidence (%d items)", len(self._ctx.evidence))
            return self._ctx.graph_context

        def _gather() -> dict[str, Any]:
            from .reporting import build_graph_context

            _log.info(
                "Coordinator: gathering evidence (countries=%s, strict=%s, limit=%d)",
                self.countries,
                self.strict_filters,
                self.limit_events,
            )

            graph_context = build_graph_context(
                countries=self.countries,
                disaster_types=self.disaster_types,
                limit_cycles=self.limit_cycles,
                limit_events=self.limit_events,
                max_age_days=self.max_age_days,
                path=self.db_path,
                strict_filters=self.strict_filters,
                country_min_events=self.country_min_events,
                max_per_connector=self.max_per_connector,
                max_per_source=self.max_per_source,
            )

            self._ctx.graph_context = graph_context
            self._ctx.evidence = graph_context.get("evidence", [])
            self._ctx.meta = graph_context.get("meta", {})
            self._ctx.evidence_at = datetime.now(UTC).isoformat()

            _log.info(
                "Coordinator: gathered %d evidence items from %d cycles",
                len(self._ctx.evidence),
                self._ctx.meta.get("cycles_analyzed", 0),
            )
            return graph_context

        return self._run_stage("evidence", _gather)

    # ── Stage 2: Ontology Construction ───────────────────────────────

    def build_ontology(
        self,
        *,
        admin_hierarchy: dict[str, list[str]] | None = None,
        force: bool = False,
    ) -> Any:
        """Build (or return cached) ``HumanitarianOntologyGraph``.

        Automatically calls ``gather_evidence()`` if evidence is not yet
        available.
        """
        if self._ctx.ontology is not None and not force:
            _log.debug("Coordinator: returning cached ontology")
            return self._ctx.ontology

        if not self._ctx.evidence:
            self.gather_evidence()

        def _build() -> Any:
            from .graph_ontology import build_ontology_from_evidence

            _log.info("Coordinator: building ontology from %d evidence items", len(self._ctx.evidence))

            ontology = build_ontology_from_evidence(
                evidence=self._ctx.evidence,
                meta=self._ctx.meta,
                admin_hierarchy=admin_hierarchy,
            )

            self._ctx.ontology = ontology
            self._ctx.ontology_at = datetime.now(UTC).isoformat()

            # Stage diagnostics
            diag = self._ctx.stage_diagnostics.get("ontology", {})
            diag["impact_count"] = len(ontology.impacts)
            diag["need_count"] = len(ontology.needs)
            diag["risk_count"] = len(ontology.risks)
            diag["response_count"] = len(ontology.responses)
            diag["geo_count"] = len(ontology.geo_areas)
            self._ctx.stage_diagnostics["ontology"] = diag

            return ontology

        return self._run_stage("ontology", _build)

    # ── Stage 3a: Long-Form Report ───────────────────────────────────

    def render_report(
        self,
        *,
        title: str = "Disaster Intelligence Report",
        use_llm: bool = False,
        template_path: Path | None = None,
    ) -> str:
        """Render the long-form report from shared evidence.

        Automatically gathers evidence if not yet available.
        """
        if not self._ctx.evidence:
            self.gather_evidence()

        def _render() -> str:
            from .reporting import render_long_form_report

            _log.info("Coordinator: rendering report (llm=%s)", use_llm)
            report = render_long_form_report(
                graph_context=self._ctx.graph_context,
                title=title,
                use_llm=use_llm,
                template_path=template_path,
            )

            self._ctx.report_md = report
            self._ctx.report_at = datetime.now(UTC).isoformat()
            return report

        return self._run_stage("report", _render)

    # ── Stage 3b: Situation Analysis ─────────────────────────────────

    def render_situation_analysis(
        self,
        *,
        title: str = "Situation Analysis",
        event_name: str = "",
        event_type: str = "",
        period: str = "",
        admin_hierarchy: dict[str, list[str]] | None = None,
        template_path: Path | None = None,
        use_llm: bool = False,
    ) -> str:
        """Render the OCHA Situation Analysis from shared evidence.

        Uses the same ``graph_context`` as the report — no redundant
        DB query.  Automatically gathers evidence if not yet available.
        """
        if not self._ctx.evidence:
            self.gather_evidence()

        def _render_sa() -> str:
            from .situation_analysis import render_situation_analysis

            _log.info("Coordinator: rendering SA (event=%s, llm=%s)", event_name, use_llm)
            sa = render_situation_analysis(
                graph_context=self._ctx.graph_context,
                title=title,
                event_name=event_name,
                event_type=event_type,
                period=period,
                admin_hierarchy=admin_hierarchy,
                template_path=template_path,
                use_llm=use_llm,
            )

            self._ctx.sa_md = sa
            self._ctx.sa_at = datetime.now(UTC).isoformat()
            return sa

        return self._run_stage("sa", _render_sa)

    # ── Report quality evaluation ────────────────────────────────────

    def evaluate_report_quality(
        self,
        *,
        min_citation_density: float = 0.0,
        required_sections: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run quality evaluation on the rendered report."""
        if not self._ctx.report_md:
            raise RuntimeError("No report rendered yet — call render_report() first")

        from .reporting import evaluate_report_quality

        quality = evaluate_report_quality(
            report_markdown=self._ctx.report_md,
            min_citation_density=min_citation_density,
            required_sections=required_sections or [],
        )
        self._ctx.report_quality = quality
        return quality

    # ── File output ──────────────────────────────────────────────────

    def write_report(self, *, output_path: Path | None = None) -> Path:
        """Write the rendered report to disk."""
        if not self._ctx.report_md:
            raise RuntimeError("No report rendered yet — call render_report() first")

        from .reporting import write_report_file

        out = write_report_file(
            report_markdown=self._ctx.report_md,
            output_path=output_path,
        )
        self._ctx.report_path = out
        return out

    def write_sa(self, *, output_path: Path | None = None) -> Path:
        """Write the rendered SA to disk."""
        if not self._ctx.sa_md:
            raise RuntimeError("No SA rendered yet — call render_situation_analysis() first")

        from .reporting import write_report_file

        out = write_report_file(
            report_markdown=self._ctx.sa_md,
            output_path=output_path,
        )
        self._ctx.sa_path = out
        return out

    # ── Stage 5: Ontology Persistence (Phase 4) ─────────────────────

    def persist_ontology(self) -> dict[str, int]:
        """Persist the current ontology graph to the database.

        Returns a dict of ``{node_type: count}`` for diagnostics.
        Must be called after ``build_ontology()``.
        """
        if self._ctx.ontology is None:
            raise RuntimeError("No ontology built yet — call build_ontology() first")

        def _persist() -> dict[str, int]:
            from .database import persist_ontology as _db_persist

            counts = _db_persist(self.engine, self._ctx.ontology)
            _log.info("Coordinator: persisted ontology — %s", counts)
            return counts

        return self._run_stage("persist_ontology", _persist)

    # ── Full Pipeline ────────────────────────────────────────────────

    def run_pipeline(
        self,
        *,
        # Report options
        report_title: str = "Disaster Intelligence Report",
        report_template_path: Path | None = None,
        # SA options
        sa_title: str = "Situation Analysis",
        event_name: str = "",
        event_type: str = "",
        period: str = "",
        admin_hierarchy: dict[str, list[str]] | None = None,
        sa_template_path: Path | None = None,
        # Shared options
        use_llm: bool = False,
        write_files: bool = True,
        output_dir: Path | None = None,
        persist_ontology: bool = False,
    ) -> PipelineContext:
        """Run the full pipeline: evidence → ontology → report + SA.

        Returns the completed ``PipelineContext`` with all outputs populated.
        Stage errors are accumulated rather than halting the pipeline — downstream
        stages are skipped if their dependencies are missing.
        """
        _log.info("Coordinator: starting full pipeline run")
        self._notify("pipeline", "started", {"stages": ["evidence", "ontology", "report", "sa"]})

        # 1. Gather evidence (single query)
        try:
            self.gather_evidence()
        except Exception:
            _log.error("Coordinator: evidence stage failed — pipeline cannot continue")
            self._ctx.finished_at = datetime.now(UTC).isoformat()
            return self._ctx

        # 2. Build ontology (used by SA, available for inspection)
        try:
            self.build_ontology(admin_hierarchy=admin_hierarchy)
        except Exception:
            _log.warning("Coordinator: ontology stage failed — continuing to report")

        # 3. Render report
        try:
            self.render_report(
                title=report_title,
                use_llm=use_llm,
                template_path=report_template_path,
            )
        except Exception:
            _log.warning("Coordinator: report stage failed — continuing to SA")

        # 4. Render SA
        try:
            self.render_situation_analysis(
                title=sa_title,
                event_name=event_name,
                event_type=event_type,
                period=period,
                admin_hierarchy=admin_hierarchy,
                template_path=sa_template_path,
                use_llm=use_llm,
            )
        except Exception:
            _log.warning("Coordinator: SA stage failed")

        # 5. Persist ontology (optional)
        if persist_ontology and self._ctx.ontology is not None:
            try:
                self.persist_ontology()
            except Exception:
                _log.warning("Coordinator: ontology persistence failed")

        # 6. Write files
        if write_files:
            try:
                if self._ctx.report_md:
                    self.write_report(
                        output_path=(output_dir / "report.md") if output_dir else None,
                    )
            except Exception:
                self._ctx.stage_errors["write"].append("Failed to write report file")
            try:
                if self._ctx.sa_md:
                    self.write_sa(
                        output_path=(output_dir / "situation-analysis.md") if output_dir else None,
                    )
            except Exception:
                self._ctx.stage_errors["write"].append("Failed to write SA file")

        self._ctx.finished_at = datetime.now(UTC).isoformat()
        self._notify("pipeline", "completed", {
            "errors": self._ctx.total_errors,
            "stages_completed": len(self._ctx.stage_diagnostics),
        })
        _log.info(
            "Coordinator: pipeline complete — report=%s, sa=%s, errors=%d",
            self._ctx.report_path,
            self._ctx.sa_path,
            self._ctx.total_errors,
        )
        return self._ctx

    # ── JSON summary for CLI / API ───────────────────────────────────

    def summary_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable summary of the pipeline run."""
        return {
            "status": "ok" if self._ctx.evidence and not self._ctx.has_errors else (
                "partial" if self._ctx.evidence else "empty"
            ),
            "meta": self._ctx.meta,
            "evidence_count": len(self._ctx.evidence),
            "ontology_built": self._ctx.ontology is not None,
            "report_path": str(self._ctx.report_path) if self._ctx.report_path else None,
            "sa_path": str(self._ctx.sa_path) if self._ctx.sa_path else None,
            "report_quality": self._ctx.report_quality or None,
            "timing": {
                "started_at": self._ctx.started_at,
                "evidence_at": self._ctx.evidence_at,
                "ontology_at": self._ctx.ontology_at,
                "report_at": self._ctx.report_at,
                "sa_at": self._ctx.sa_at,
                "finished_at": self._ctx.finished_at,
            },
            "stage_diagnostics": dict(self._ctx.stage_diagnostics),
            "stage_errors": {k: list(v) for k, v in self._ctx.stage_errors.items() if v},
            "total_errors": self._ctx.total_errors,
        }
