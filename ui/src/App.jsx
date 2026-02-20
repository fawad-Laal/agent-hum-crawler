import { useEffect, useMemo, useState } from "react";

const defaultForm = {
  countries: "Ethiopia",
  disaster_types: "epidemic/disease outbreak,flood,conflict emergency,drought",
  max_age_days: 30,
  limit: 10,
  limit_cycles: 20,
  limit_events: 30,
  country_min_events: 1,
  max_per_connector: 8,
  max_per_source: 4,
  report_template: "config/report_template.brief.json",
  use_llm: false,
  // Situation Analysis fields
  sa_title: "Situation Analysis",
  sa_event_name: "",
  sa_event_type: "",
  sa_period: "",
  sa_template: "config/report_template.situation_analysis.json",
  sa_limit_events: 80,
  // Pipeline fields
  pipeline_report_title: "Disaster Intelligence Report",
  pipeline_sa_title: "Situation Analysis",
  pipeline_event_name: "",
  pipeline_event_type: "",
  pipeline_period: "",
};

function fmtNumber(v, digits = 3) {
  if (v === null || v === undefined) return "-";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  if (Math.abs(n) < 1) return n.toFixed(digits);
  return n.toLocaleString();
}

function formatMatchReasons(reasons) {
  const r = reasons || {};
  const country = Number(r.country_miss || 0);
  const hazard = Number(r.hazard_miss || 0);
  const age = Number(r.age_filtered || 0);
  return `country:${country} | hazard:${hazard} | age:${age}`;
}

function freshnessTone(status) {
  if (status === "fresh") return "ok";
  if (status === "stale") return "fail";
  return "muted";
}

function TinyLineChart({ values, color = "#1ec97e", yMax = null }) {
  const width = 260;
  const height = 70;
  if (!values.length) return <div className="muted">No data</div>;
  const max = yMax ?? Math.max(...values, 1);
  const min = 0;
  const stepX = values.length > 1 ? width / (values.length - 1) : width;
  const points = values
    .map((v, i) => {
      const x = i * stepX;
      const y = height - ((v - min) / (max - min || 1)) * height;
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <svg width={width} height={height} className="spark">
      <polyline fill="none" stroke={color} strokeWidth="2.5" points={points} />
    </svg>
  );
}

function buildSourceCheckFromConnectorMetrics(payload) {
  const metrics = Array.isArray(payload?.connector_metrics) ? payload.connector_metrics : [];
  const sourceChecks = [];
  for (const metric of metrics) {
    const connector = metric?.connector || "unknown";
    const sources = Array.isArray(metric?.source_results) ? metric.source_results : [];
    for (const s of sources) {
      const status = String(s?.status || "unknown");
      const fetched = Number(s?.fetched_count || 0);
      sourceChecks.push({
        connector,
        source_name: String(s?.source_name || ""),
        source_url: String(s?.source_url || ""),
        status,
        fetched_count: fetched,
        matched_count: Number(s?.matched_count || 0),
        error: String(s?.error || ""),
        latest_published_at: s?.latest_published_at || null,
        latest_age_days: s?.latest_age_days,
        freshness_status: String(s?.freshness_status || "unknown"),
        stale_streak: Number(s?.stale_streak || 0),
        stale_action: s?.stale_action || null,
        match_reasons: s?.match_reasons || {},
        working: (status === "ok" || status === "recovered") && fetched > 0,
      });
    }
  }
  return {
    status: "ok",
    connector_count: Number(payload?.connector_count || metrics.length || 0),
    raw_item_count: Number(payload?.raw_item_count || 0),
    working_sources: sourceChecks.filter((x) => x.working).length,
    total_sources: sourceChecks.length,
    source_checks: sourceChecks,
    connector_metrics: metrics,
  };
}

/* ═══════════════════════════════════════════════════════════════════ */

export default function App() {
  const [overview, setOverview] = useState(null);
  const [reports, setReports] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [form, setForm] = useState(defaultForm);
  const [busy, setBusy] = useState(false);
  const [workbenchBusy, setWorkbenchBusy] = useState(false);
  const [actionOutput, setActionOutput] = useState(null);
  const [workbench, setWorkbench] = useState(null);
  const [profileStore, setProfileStore] = useState({ presets: {}, last_profile: null });
  const [sourceCheck, setSourceCheck] = useState(null);
  const [autoSourceCheck, setAutoSourceCheck] = useState(true);
  const [presetName, setPresetName] = useState("");
  const [selectedPreset, setSelectedPreset] = useState("");
  const [error, setError] = useState("");
  const [saOutput, setSaOutput] = useState(null);
  const [systemInfo, setSystemInfo] = useState(null);
  const [countrySources, setCountrySources] = useState(null);
  const [pipelineOutput, setPipelineOutput] = useState(null);
  const [pipelineBusy, setPipelineBusy] = useState(false);
  const [connectorDiag, setConnectorDiag] = useState(null);
  const [selectedHazards, setSelectedHazards] = useState(
    new Set(defaultForm.disaster_types.split(",").map((s) => s.trim()))
  );

  /* ── Fetchers ─────────────────────────────────────────────── */

  async function fetchOverview() {
    setError("");
    const r = await fetch("/api/overview");
    const data = await r.json();
    setOverview(data);
    const flags = data?.feature_flags || {};
    if (typeof flags.dashboard_auto_source_check_default === "boolean") {
      setAutoSourceCheck(flags.dashboard_auto_source_check_default);
    }
    if (
      Number.isFinite(Number(flags.max_item_age_days_default)) &&
      Number(flags.max_item_age_days_default) > 0
    ) {
      setForm((s) => ({ ...s, max_age_days: Number(flags.max_item_age_days_default) }));
    }
  }

  async function fetchReports() {
    const r = await fetch("/api/reports");
    const data = await r.json();
    setReports(data.reports || []);
  }

  async function fetchReport(name) {
    const r = await fetch(`/api/reports/${encodeURIComponent(name)}`);
    const data = await r.json();
    setSelectedReport(data);
  }

  async function fetchWorkbenchProfiles() {
    const r = await fetch("/api/workbench-profiles");
    const data = await r.json();
    setProfileStore(data || { presets: {}, last_profile: null });
  }

  async function fetchSystemInfo() {
    try {
      const r = await fetch("/api/system-info");
      const data = await r.json();
      setSystemInfo(data);
    } catch (_) {
      /* ignore */
    }
  }

  async function fetchCountrySources() {
    try {
      const r = await fetch("/api/country-sources");
      const data = await r.json();
      setCountrySources(data);
    } catch (_) {
      /* ignore */
    }
  }

  useEffect(() => {
    void fetchOverview().catch((e) => setError(String(e)));
    void fetchReports().catch((e) => setError(String(e)));
    void fetchWorkbenchProfiles().catch((e) => setError(String(e)));
    void fetchSystemInfo();
    void fetchCountrySources();
  }, []);

  /* ── Derived values ───────────────────────────────────────── */

  const quality = overview?.quality || {};
  const hardening = overview?.hardening || {};
  const sourceHealth = overview?.source_health || {};
  const cycles = Array.isArray(overview?.cycles) ? overview.cycles : [];
  const e2e = overview?.latest_e2e_summary || {};
  const qualityTrend = Array.isArray(overview?.quality_trend) ? overview.quality_trend : [];
  const flags = overview?.feature_flags || {};

  const trend = useMemo(() => {
    const ordered = [...cycles].reverse();
    return {
      events: ordered.map((c) => Number(c.event_count || 0)),
      llmEnriched: ordered.map((c) => Number(c.llm_enriched_count || 0)),
      llmFallback: ordered.map((c) => Number(c.llm_fallback_count || 0)),
      llmValidationFails: ordered.map((c) => Number(c.llm_validation_fail_count || 0)),
    };
  }, [cycles]);

  const qualityRateTrend = useMemo(() => {
    return {
      duplicate: qualityTrend.map((x) => Number(x.duplicate_rate_estimate || 0)),
      traceable: qualityTrend.map((x) => Number(x.traceable_rate || 0)),
      llmEnrichment: qualityTrend.map((x) => Number(x.llm_enrichment_rate || 0)),
      citationCoverage: qualityTrend.map((x) => Number(x.citation_coverage_rate || 0)),
    };
  }, [qualityTrend]);

  const lastActionSummary = useMemo(() => {
    if (!actionOutput) return { label: "No action yet", tone: "muted" };
    if (actionOutput?.status === "error") return { label: "Failed", tone: "fail" };
    if (actionOutput?.cycle_id !== undefined) {
      return { label: `Cycle ran (cycle_id=${actionOutput.cycle_id})`, tone: "ok" };
    }
    if (actionOutput?.output_path || actionOutput?.report_path) {
      return { label: "Report generated", tone: "ok" };
    }
    return { label: "Completed", tone: "ok" };
  }, [actionOutput]);

  const topFailingSources = useMemo(() => {
    const list = Array.isArray(sourceHealth.sources) ? sourceHealth.sources : [];
    return [...list]
      .sort((a, b) => Number(b.failure_rate || 0) - Number(a.failure_rate || 0))
      .slice(0, 8);
  }, [sourceHealth]);

  /* ── Handlers ─────────────────────────────────────────────── */

  async function handleRunCycle() {
    setBusy(true);
    setError("");
    try {
      const r = await fetch("/api/run-cycle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          countries: form.countries,
          disaster_types: form.disaster_types,
          max_age_days: form.max_age_days,
          limit: form.limit,
        }),
      });
      const data = await r.json();
      setActionOutput(data);
      if (Array.isArray(data?.connector_metrics)) {
        setSourceCheck(buildSourceCheckFromConnectorMetrics(data));
        setConnectorDiag(parseConnectorDiagnostics(data));
      }
      if (autoSourceCheck) {
        const checkResp = await fetch("/api/source-check", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            countries: form.countries,
            disaster_types: form.disaster_types,
            max_age_days: form.max_age_days,
            limit: form.limit,
          }),
        });
        const checkData = await checkResp.json();
        setSourceCheck(checkData);
      }
      await fetchOverview();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleWriteReport() {
    setBusy(true);
    setError("");
    try {
      const r = await fetch("/api/write-report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          countries: form.countries,
          disaster_types: form.disaster_types,
          max_age_days: form.max_age_days,
          country_min_events: form.country_min_events,
          max_per_connector: form.max_per_connector,
          max_per_source: form.max_per_source,
          limit_cycles: form.limit_cycles,
          limit_events: form.limit_events,
          report_template: form.report_template,
          use_llm: form.use_llm,
        }),
      });
      const data = await r.json();
      setActionOutput(data);
      await fetchReports();
      await fetchOverview();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleRunWorkbench() {
    setWorkbenchBusy(true);
    setError("");
    try {
      const r = await fetch("/api/report-workbench", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          countries: form.countries,
          disaster_types: form.disaster_types,
          max_age_days: form.max_age_days,
          country_min_events: form.country_min_events,
          max_per_connector: form.max_per_connector,
          max_per_source: form.max_per_source,
          limit_cycles: form.limit_cycles,
          limit_events: form.limit_events,
          report_template: form.report_template,
        }),
      });
      const data = await r.json();
      setWorkbench(data);
      await fetchWorkbenchProfiles();
      await fetchReports();
      await fetchOverview();
    } catch (e) {
      setError(String(e));
    } finally {
      setWorkbenchBusy(false);
    }
  }

  function currentProfileFromForm() {
    return {
      countries: form.countries,
      disaster_types: form.disaster_types,
      max_age_days: form.max_age_days,
      country_min_events: form.country_min_events,
      max_per_connector: form.max_per_connector,
      max_per_source: form.max_per_source,
      limit_cycles: form.limit_cycles,
      limit_events: form.limit_events,
      report_template: form.report_template,
    };
  }

  function applyProfile(profile) {
    if (!profile) return;
    setForm((s) => ({
      ...s,
      countries: profile.countries ?? s.countries,
      disaster_types: profile.disaster_types ?? s.disaster_types,
      max_age_days: Number(profile.max_age_days ?? s.max_age_days),
      country_min_events: Number(profile.country_min_events ?? s.country_min_events),
      max_per_connector: Number(profile.max_per_connector ?? s.max_per_connector),
      max_per_source: Number(profile.max_per_source ?? s.max_per_source),
      limit_cycles: Number(profile.limit_cycles ?? s.limit_cycles),
      limit_events: Number(profile.limit_events ?? s.limit_events),
      report_template: profile.report_template ?? s.report_template,
    }));
  }

  async function handleSavePreset() {
    const name = presetName.trim();
    if (!name) {
      setError("Preset name is required.");
      return;
    }
    setError("");
    const r = await fetch("/api/workbench-profiles/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, profile: currentProfileFromForm() }),
    });
    const data = await r.json();
    if (!r.ok) {
      setError(data.error || "Failed to save preset.");
      return;
    }
    setProfileStore(data.store || { presets: {}, last_profile: null });
    setSelectedPreset(name);
  }

  async function handleDeletePreset() {
    if (!selectedPreset) return;
    setError("");
    const r = await fetch("/api/workbench-profiles/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: selectedPreset }),
    });
    const data = await r.json();
    if (!r.ok) {
      setError(data.error || "Failed to delete preset.");
      return;
    }
    setProfileStore(data.store || { presets: {}, last_profile: null });
    setSelectedPreset("");
  }

  async function handleRerunLastProfile() {
    setWorkbenchBusy(true);
    setError("");
    try {
      const r = await fetch("/api/report-workbench/rerun-last", { method: "POST" });
      const data = await r.json();
      setWorkbench(data);
      applyProfile(data.profile);
      await fetchWorkbenchProfiles();
      await fetchReports();
      await fetchOverview();
    } catch (e) {
      setError(String(e));
    } finally {
      setWorkbenchBusy(false);
    }
  }

  async function handleWriteSituationAnalysis() {
    setBusy(true);
    setError("");
    try {
      const r = await fetch("/api/write-situation-analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          countries: form.countries,
          disaster_types: form.disaster_types,
          title: form.sa_title,
          event_name: form.sa_event_name,
          event_type: form.sa_event_type,
          period: form.sa_period,
          sa_template: form.sa_template,
          limit_cycles: form.limit_cycles,
          limit_events: form.sa_limit_events,
          max_age_days: form.max_age_days,
          use_llm: form.use_llm,
        }),
      });
      const data = await r.json();
      setActionOutput(data);
      setSaOutput(data);
      await fetchReports();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleSourceCheck() {
    setBusy(true);
    setError("");
    try {
      const r = await fetch("/api/source-check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          countries: form.countries,
          disaster_types: form.disaster_types,
          max_age_days: form.max_age_days,
          limit: form.limit,
        }),
      });
      const data = await r.json();
      setSourceCheck(data);
      setActionOutput(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleRunPipeline() {
    setPipelineBusy(true);
    setError("");
    try {
      const r = await fetch("/api/run-pipeline", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          countries: form.countries,
          disaster_types: form.disaster_types,
          report_title: form.pipeline_report_title,
          sa_title: form.pipeline_sa_title,
          event_name: form.pipeline_event_name,
          event_type: form.pipeline_event_type,
          period: form.pipeline_period,
          limit_cycles: form.limit_cycles,
          limit_events: form.limit_events,
          max_age_days: form.max_age_days,
          use_llm: form.use_llm,
        }),
      });
      const data = await r.json();
      setPipelineOutput(data);
      setActionOutput(data);
      await fetchReports();
      await fetchOverview();
    } catch (e) {
      setError(String(e));
    } finally {
      setPipelineBusy(false);
    }
  }

  function toggleHazard(hazard) {
    setSelectedHazards((prev) => {
      const next = new Set(prev);
      if (next.has(hazard)) {
        next.delete(hazard);
      } else {
        next.add(hazard);
      }
      const joined = [...next].join(",");
      setForm((s) => ({ ...s, disaster_types: joined }));
      return next;
    });
  }

  function selectCountryPreset(countryName) {
    setForm((s) => ({ ...s, countries: countryName }));
  }

  function parseConnectorDiagnostics(payload) {
    const metrics = Array.isArray(payload?.connector_metrics) ? payload.connector_metrics : [];
    const summary = metrics.map((m) => ({
      connector: m.connector || "unknown",
      attempted: m.attempted_sources || 0,
      healthy: m.healthy_sources || 0,
      failed: m.failed_sources || 0,
      fetched: m.fetched_count || 0,
      matched: m.matched_count || 0,
      errors: m.errors || [],
      warnings: m.warnings || [],
      sources: (m.source_results || []).map((s) => ({
        name: s.source_name || "",
        url: s.source_url || "",
        status: s.status || "unknown",
        fetched: s.fetched_count || 0,
        matched: s.matched_count || 0,
        match_reasons: s.match_reasons || {},
        freshness: s.freshness_status || "unknown",
        age_days: s.latest_age_days,
        stale_action: s.stale_action,
      })),
    }));
    return { connectors: summary, total_fetched: payload?.raw_item_count || 0 };
  }

  /* ═══════════════════════════════════════════════════════════════ */
  /*  RENDER                                                        */
  /* ═══════════════════════════════════════════════════════════════ */

  return (
    <main className="page">
      {/* ── Header ──────────────────────────────────────────────── */}
      <header className="top">
        <div>
          <h1>Agent HUM Crawler</h1>
          <div className="header-meta">
            <span>Multi-Hazard Intelligence Platform</span>
            {systemInfo ? (
              <span className={`chip chip-${systemInfo.rust_available ? "ok" : "muted"}`}>
                {systemInfo.rust_available ? "Rust ✓" : "Python-only"}
              </span>
            ) : null}
          </div>
        </div>
        <button className="ghost" onClick={() => void fetchOverview()}>
          Refresh
        </button>
      </header>

      {error ? <div className="error">{error}</div> : null}

      {/* ── KPIs ────────────────────────────────────────────────── */}
      <section className="grid kpis">
        <article className="card kpi">
          <div className="kpi-label">Cycles</div>
          <div className="kpi-value">{fmtNumber(quality.cycles_analyzed, 0)}</div>
        </article>
        <article className="card kpi">
          <div className="kpi-label">Events</div>
          <div className="kpi-value">{fmtNumber(quality.events_analyzed, 0)}</div>
        </article>
        <article className="card kpi">
          <div className="kpi-label">Dup Rate</div>
          <div className="kpi-value">{fmtNumber(quality.duplicate_rate_estimate)}</div>
        </article>
        <article className="card kpi">
          <div className="kpi-label">Traceable</div>
          <div className="kpi-value">{fmtNumber(quality.traceable_rate)}</div>
        </article>
        <article className="card kpi">
          <div className="kpi-label">Hardening</div>
          <div className={`kpi-value status-${hardening.status || "unknown"}`}>
            {hardening.status || "-"}
          </div>
        </article>
      </section>

      {/* ── Command Center ──────────────────────────────────────── */}
      <section className="grid">
        <article className="card command-center">
          <h2>Command Center</h2>

          {/* Target: Country */}
          <div className="cc-section">
            <div className="cc-label">Country</div>
            <div className="chip-row">
              {(countrySources?.countries || []).map((c) => (
                <button
                  key={c.country}
                  className={`chip-btn ${form.countries === c.country ? "chip-active" : ""}`}
                  onClick={() => selectCountryPreset(c.country)}
                >
                  {c.country}{" "}
                  <span className="chip-count">
                    {c.feed_count + (countrySources?.global_feed_count || 0)}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Target: Hazard Types */}
          <div className="cc-section">
            <div className="cc-label">Hazard Types</div>
            <div className="chip-row">
              {(systemInfo?.allowed_disaster_types || []).map((h) => (
                <button
                  key={h}
                  className={`chip-btn ${selectedHazards.has(h) ? "chip-active" : ""}`}
                  onClick={() => toggleHazard(h)}
                >
                  {h}
                </button>
              ))}
            </div>
            <div className="cc-meta">
              {selectedHazards.size} type{selectedHazards.size !== 1 ? "s" : ""} &middot;{" "}
              {countrySources?.global_feed_count || 0} global feeds
            </div>
          </div>

          {/* Action Buttons */}
          <div className="action-groups">
            <div className="action-group">
              <div className="action-group-label">Collection</div>
              <div className="actions">
                <button disabled={busy} onClick={() => void handleRunCycle()}>
                  {busy ? "Running\u2026" : "Run Cycle"}
                </button>
                <button disabled={busy} className="ghost" onClick={() => void handleSourceCheck()}>
                  {busy ? "Checking\u2026" : "Source Check"}
                </button>
              </div>
            </div>
            <div className="action-group">
              <div className="action-group-label">Reports</div>
              <div className="actions">
                <button disabled={busy} className="accent" onClick={() => void handleWriteReport()}>
                  {busy ? "Working\u2026" : "Write Report"}
                </button>
                <button
                  disabled={busy}
                  className="accent"
                  onClick={() => void handleWriteSituationAnalysis()}
                >
                  {busy ? "Working\u2026" : "Write SA"}
                </button>
              </div>
            </div>
            <div className="action-group">
              <div className="action-group-label">Workbench</div>
              <div className="actions">
                <button disabled={workbenchBusy} onClick={() => void handleRunWorkbench()}>
                  {workbenchBusy ? "Comparing\u2026" : "AI vs Deterministic"}
                </button>
                <button
                  disabled={workbenchBusy}
                  className="ghost"
                  onClick={() => void handleRerunLastProfile()}
                >
                  {workbenchBusy ? "Running\u2026" : "Rerun Last"}
                </button>
              </div>
            </div>
            <div className="action-group">
              <div className="action-group-label">Pipeline</div>
              <div className="actions">
                <button
                  disabled={pipelineBusy}
                  className="pipeline-btn"
                  onClick={() => void handleRunPipeline()}
                >
                  {pipelineBusy ? "Pipeline Running\u2026" : "\u25B6 Run Pipeline"}
                </button>
              </div>
            </div>
          </div>

          {/* ── Collapsible parameter groups ──────────────────── */}
          <div className="cc-params">
            <details>
              <summary>Collection Parameters</summary>
              <div className="cc-params-body">
                <div className="row">
                  <label>
                    Countries
                    <input
                      value={form.countries}
                      onChange={(e) => setForm((s) => ({ ...s, countries: e.target.value }))}
                    />
                  </label>
                  <label>
                    Disaster Types
                    <input
                      value={form.disaster_types}
                      onChange={(e) => setForm((s) => ({ ...s, disaster_types: e.target.value }))}
                    />
                  </label>
                </div>
                <div className="row">
                  <label>
                    Limit
                    <input
                      type="number"
                      value={form.limit}
                      onChange={(e) => setForm((s) => ({ ...s, limit: Number(e.target.value) }))}
                    />
                  </label>
                  <label>
                    Max Age Days
                    <input
                      type="number"
                      value={form.max_age_days}
                      onChange={(e) =>
                        setForm((s) => ({ ...s, max_age_days: Number(e.target.value) }))
                      }
                    />
                  </label>
                  <label>
                    Max / Connector
                    <input
                      type="number"
                      value={form.max_per_connector}
                      onChange={(e) =>
                        setForm((s) => ({ ...s, max_per_connector: Number(e.target.value) }))
                      }
                    />
                  </label>
                  <label>
                    Max / Source
                    <input
                      type="number"
                      value={form.max_per_source}
                      onChange={(e) =>
                        setForm((s) => ({ ...s, max_per_source: Number(e.target.value) }))
                      }
                    />
                  </label>
                </div>
              </div>
            </details>

            <details>
              <summary>Report Settings</summary>
              <div className="cc-params-body">
                <div className="row">
                  <label>
                    Limit Cycles
                    <input
                      type="number"
                      value={form.limit_cycles}
                      onChange={(e) =>
                        setForm((s) => ({ ...s, limit_cycles: Number(e.target.value) }))
                      }
                    />
                  </label>
                  <label>
                    Limit Events
                    <input
                      type="number"
                      value={form.limit_events}
                      onChange={(e) =>
                        setForm((s) => ({ ...s, limit_events: Number(e.target.value) }))
                      }
                    />
                  </label>
                  <label>
                    Country Min Events
                    <input
                      type="number"
                      value={form.country_min_events}
                      onChange={(e) =>
                        setForm((s) => ({ ...s, country_min_events: Number(e.target.value) }))
                      }
                    />
                  </label>
                </div>
                <label>
                  Template
                  <select
                    value={form.report_template}
                    onChange={(e) =>
                      setForm((s) => ({ ...s, report_template: e.target.value }))
                    }
                  >
                    <option value="config/report_template.brief.json">Brief</option>
                    <option value="config/report_template.detailed.json">Detailed</option>
                    <option value="config/report_template.json">Default</option>
                    <option value="config/report_template.situation_analysis.json">
                      Situation Analysis
                    </option>
                  </select>
                </label>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={form.use_llm}
                    onChange={(e) => setForm((s) => ({ ...s, use_llm: e.target.checked }))}
                  />
                  Use LLM for report drafting
                </label>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={autoSourceCheck}
                    onChange={(e) => setAutoSourceCheck(e.target.checked)}
                  />
                  Auto-run Source Check after Run Cycle
                </label>
              </div>
            </details>

            <details>
              <summary>Situation Analysis Parameters</summary>
              <div className="cc-params-body">
                <label>
                  SA Title
                  <input
                    value={form.sa_title}
                    onChange={(e) => setForm((s) => ({ ...s, sa_title: e.target.value }))}
                  />
                </label>
                <label>
                  Event Name
                  <input
                    value={form.sa_event_name}
                    onChange={(e) => setForm((s) => ({ ...s, sa_event_name: e.target.value }))}
                    placeholder="e.g. Tropical Cyclone Gezani-26"
                  />
                </label>
                <div className="row">
                  <label>
                    Event Type
                    <input
                      value={form.sa_event_type}
                      onChange={(e) => setForm((s) => ({ ...s, sa_event_type: e.target.value }))}
                      placeholder="e.g. cyclone/storm"
                    />
                  </label>
                  <label>
                    Period
                    <input
                      value={form.sa_period}
                      onChange={(e) => setForm((s) => ({ ...s, sa_period: e.target.value }))}
                      placeholder="e.g. 2-6 March 2026"
                    />
                  </label>
                </div>
                <div className="row">
                  <label>
                    SA Limit Events
                    <input
                      type="number"
                      value={form.sa_limit_events}
                      onChange={(e) =>
                        setForm((s) => ({ ...s, sa_limit_events: Number(e.target.value) }))
                      }
                    />
                  </label>
                  <label>
                    SA Template
                    <select
                      value={form.sa_template}
                      onChange={(e) => setForm((s) => ({ ...s, sa_template: e.target.value }))}
                    >
                      <option value="config/report_template.situation_analysis.json">
                        Situation Analysis
                      </option>
                    </select>
                  </label>
                </div>
              </div>
            </details>

            <details>
              <summary>Pipeline Parameters</summary>
              <div className="cc-params-body">
                <div className="row">
                  <label>
                    Report Title
                    <input
                      value={form.pipeline_report_title}
                      onChange={(e) =>
                        setForm((s) => ({ ...s, pipeline_report_title: e.target.value }))
                      }
                    />
                  </label>
                  <label>
                    SA Title
                    <input
                      value={form.pipeline_sa_title}
                      onChange={(e) =>
                        setForm((s) => ({ ...s, pipeline_sa_title: e.target.value }))
                      }
                    />
                  </label>
                </div>
                <div className="row">
                  <label>
                    Event Name
                    <input
                      value={form.pipeline_event_name}
                      onChange={(e) =>
                        setForm((s) => ({ ...s, pipeline_event_name: e.target.value }))
                      }
                      placeholder="auto-inferred if empty"
                    />
                  </label>
                  <label>
                    Event Type
                    <input
                      value={form.pipeline_event_type}
                      onChange={(e) =>
                        setForm((s) => ({ ...s, pipeline_event_type: e.target.value }))
                      }
                      placeholder="e.g. disease outbreak"
                    />
                  </label>
                  <label>
                    Period
                    <input
                      value={form.pipeline_period}
                      onChange={(e) =>
                        setForm((s) => ({ ...s, pipeline_period: e.target.value }))
                      }
                      placeholder="e.g. Feb 2026"
                    />
                  </label>
                </div>
              </div>
            </details>

            <details>
              <summary>Presets</summary>
              <div className="cc-params-body">
                <label>
                  Saved Presets
                  <select
                    value={selectedPreset}
                    onChange={(e) => {
                      const name = e.target.value;
                      setSelectedPreset(name);
                      if (name && profileStore?.presets?.[name]) {
                        applyProfile(profileStore.presets[name]);
                      }
                    }}
                  >
                    <option value="">Select preset\u2026</option>
                    {Object.keys(profileStore?.presets || {})
                      .sort()
                      .map((name) => (
                        <option key={name} value={name}>
                          {name}
                        </option>
                      ))}
                  </select>
                </label>
                <div className="row">
                  <label>
                    Preset Name
                    <input
                      value={presetName}
                      onChange={(e) => setPresetName(e.target.value)}
                      placeholder="e.g. madagascar-brief-cyclone"
                    />
                  </label>
                  <div className="preset-buttons">
                    <button type="button" onClick={() => void handleSavePreset()}>
                      Save
                    </button>
                    <button
                      type="button"
                      className="ghost"
                      disabled={!selectedPreset}
                      onClick={() => void handleDeletePreset()}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            </details>
          </div>
        </article>
      </section>

      {/* ── Trends ──────────────────────────────────────────────── */}
      <section className="grid two">
        <article className="card">
          <h2>Cycle Trends</h2>
          <div className="trend">
            <div>
              <div className="metric-label">Events / Cycle</div>
              <TinyLineChart values={trend.events} color="#63b3ff" />
            </div>
            <div>
              <div className="metric-label">LLM Enriched</div>
              <TinyLineChart values={trend.llmEnriched} color="#1ec97e" />
            </div>
            <div>
              <div className="metric-label">LLM Fallback</div>
              <TinyLineChart values={trend.llmFallback} color="#f4c542" />
            </div>
            <div>
              <div className="metric-label">Validation Failures</div>
              <TinyLineChart values={trend.llmValidationFails} color="#ff6565" />
            </div>
          </div>
        </article>

        <article className="card">
          <h2>Quality Rate Trends</h2>
          <div className="trend">
            <div>
              <div className="metric-label">Duplicate Rate</div>
              <TinyLineChart values={qualityRateTrend.duplicate} color="#ff6565" yMax={1} />
            </div>
            <div>
              <div className="metric-label">Traceable Rate</div>
              <TinyLineChart values={qualityRateTrend.traceable} color="#57e58e" yMax={1} />
            </div>
            <div>
              <div className="metric-label">LLM Enrichment</div>
              <TinyLineChart values={qualityRateTrend.llmEnrichment} color="#f4c542" yMax={1} />
            </div>
            <div>
              <div className="metric-label">Citation Coverage</div>
              <TinyLineChart values={qualityRateTrend.citationCoverage} color="#63b3ff" yMax={1} />
            </div>
          </div>
        </article>
      </section>

      {/* ── System Health (unified) ─────────────────────────────── */}
      <section className="grid">
        <article className="card">
          <h2>System Health</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Check</th>
                <th>Status</th>
                <th>Actual</th>
                <th>Threshold</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Duplicate rate</td>
                <td>{String(hardening?.checks?.duplicate_rate_ok)}</td>
                <td>{fmtNumber(hardening?.metrics?.duplicate_rate)}</td>
                <td>{fmtNumber(hardening?.thresholds?.max_duplicate_rate)}</td>
              </tr>
              <tr>
                <td>Traceable rate</td>
                <td>{String(hardening?.checks?.traceable_rate_ok)}</td>
                <td>{fmtNumber(hardening?.metrics?.traceable_rate)}</td>
                <td>{fmtNumber(hardening?.thresholds?.min_traceable_rate)}</td>
              </tr>
              <tr>
                <td>Connector failure</td>
                <td>{String(hardening?.checks?.connector_failure_ok)}</td>
                <td>{fmtNumber(hardening?.metrics?.worst_connector_failure_rate)}</td>
                <td>{fmtNumber(hardening?.thresholds?.max_connector_failure_rate)}</td>
              </tr>
              <tr>
                <td>LLM enrichment</td>
                <td>{String(hardening?.checks?.llm_enrichment_rate_ok)}</td>
                <td>{fmtNumber(hardening?.metrics?.llm_enrichment_rate)}</td>
                <td>{fmtNumber(hardening?.thresholds?.min_llm_enrichment_rate)}</td>
              </tr>
              <tr>
                <td>Citation coverage</td>
                <td>{String(hardening?.checks?.citation_coverage_ok)}</td>
                <td>{fmtNumber(hardening?.metrics?.citation_coverage_rate)}</td>
                <td>{fmtNumber(hardening?.thresholds?.min_citation_coverage_rate)}</td>
              </tr>
            </tbody>
          </table>

          <details className="health-details">
            <summary>Conformance &amp; Security</summary>
            <div className="kv" style={{ marginTop: "0.5rem" }}>
              <div>Latest E2E Status</div>
              <div>{e2e.status || "-"}</div>
              <div>Conformance</div>
              <div>{e2e?.checks?.conformance_status || "-"}</div>
              <div>Security</div>
              <div>{e2e?.checks?.security_status || "-"}</div>
              <div>Report Quality</div>
              <div>{e2e?.checks?.report_quality_status || "-"}</div>
              <div>Hardening</div>
              <div>{e2e?.checks?.hardening_status || "-"}</div>
              <div>Artifacts</div>
              <div className="truncate">{e2e.artifacts_dir || "-"}</div>
            </div>
          </details>

          <details className="health-details">
            <summary>Feature Flags</summary>
            <div className="kv" style={{ marginTop: "0.5rem" }}>
              <div>reliefweb_enabled</div>
              <div>{String(flags.reliefweb_enabled)}</div>
              <div>llm_enrichment_enabled</div>
              <div>{String(flags.llm_enrichment_enabled)}</div>
              <div>report_strict_filters_default</div>
              <div>{String(flags.report_strict_filters_default)}</div>
              <div>dashboard_auto_source_check_default</div>
              <div>{String(flags.dashboard_auto_source_check_default)}</div>
              <div>source_check_endpoint_enabled</div>
              <div>{String(flags.source_check_endpoint_enabled)}</div>
              <div>max_item_age_days_default</div>
              <div>{flags.max_item_age_days_default ?? "-"}</div>
              <div>stale_feed_auto_warn_enabled</div>
              <div>{String(flags.stale_feed_auto_warn_enabled)}</div>
              <div>stale_feed_warn_after_checks</div>
              <div>{flags.stale_feed_warn_after_checks ?? "-"}</div>
              <div>stale_feed_auto_demote_enabled</div>
              <div>{String(flags.stale_feed_auto_demote_enabled)}</div>
              <div>stale_feed_demote_after_checks</div>
              <div>{flags.stale_feed_demote_after_checks ?? "-"}</div>
            </div>
          </details>

          {topFailingSources.length > 0 && (
            <details className="health-details">
              <summary>Source Health Hotspots ({topFailingSources.length})</summary>
              <table className="table" style={{ marginTop: "0.5rem" }}>
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Connector</th>
                    <th>Failure Rate</th>
                    <th>Runs</th>
                  </tr>
                </thead>
                <tbody>
                  {topFailingSources.map((s) => (
                    <tr key={`${s.connector}-${s.source_name}-${s.source_url}`}>
                      <td title={s.source_url}>{s.source_name}</td>
                      <td>{s.connector}</td>
                      <td>{fmtNumber(s.failure_rate)}</td>
                      <td>{fmtNumber(s.runs, 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          )}
        </article>
      </section>

      {/* ── Action Output (unified — replaces both "Last Action Output" */}
      {/*    and separate "Pipeline Output" cards) ─────────────────────── */}
      {(actionOutput || pipelineOutput) && (
        <section className="grid">
          <article className={`card${pipelineOutput ? " pipeline-output-card" : ""}`}>
            <h2>Action Output</h2>

            {pipelineOutput ? (
              /* Pipeline-specific rich display */
              <>
                {pipelineOutput.status === "error" ? (
                  <div className="error">
                    <strong>Pipeline Error</strong>
                    <pre style={{ margin: "0.5rem 0 0" }}>
                      {pipelineOutput.stderr ||
                        pipelineOutput.stdout ||
                        JSON.stringify(pipelineOutput, null, 2)}
                    </pre>
                  </div>
                ) : (
                  <>
                    <div className="mini-stat-row">
                      <div className="mini-stat">
                        <span className="mini-stat-label">Status</span>
                        <span
                          className={`mini-stat-value ${
                            pipelineOutput.status === "ok" ? "status-pass" : "status-fail"
                          }`}
                        >
                          {pipelineOutput.status || "\u2014"}
                        </span>
                      </div>
                      <div className="mini-stat">
                        <span className="mini-stat-label">Evidence</span>
                        <span className="mini-stat-value">
                          {pipelineOutput.evidence_count ?? "\u2014"}
                        </span>
                      </div>
                      <div className="mini-stat">
                        <span className="mini-stat-label">Ontology</span>
                        <span className="mini-stat-value">
                          {pipelineOutput.ontology_built ? "\u2713" : "\u2014"}
                        </span>
                      </div>
                      {pipelineOutput.report_path && (
                        <div className="mini-stat">
                          <span className="mini-stat-label">Report</span>
                          <span className="mini-stat-value" title={pipelineOutput.report_path}>
                            \u2713 Generated
                          </span>
                        </div>
                      )}
                      {pipelineOutput.sa_path && (
                        <div className="mini-stat">
                          <span className="mini-stat-label">SA</span>
                          <span className="mini-stat-value" title={pipelineOutput.sa_path}>
                            \u2713 Generated
                          </span>
                        </div>
                      )}
                    </div>
                    {pipelineOutput.timing && (
                      <div className="timing-line">
                        {pipelineOutput.timing.started_at || "\u2014"} \u2192{" "}
                        {pipelineOutput.timing.finished_at || "\u2014"}
                      </div>
                    )}
                  </>
                )}
                <details>
                  <summary style={{ cursor: "pointer" }}>Full JSON</summary>
                  <pre style={{ maxHeight: "400px", overflow: "auto" }}>
                    {JSON.stringify(pipelineOutput, null, 2)}
                  </pre>
                </details>
              </>
            ) : (
              /* Generic action output */
              <>
                <div className={`status-inline status-${lastActionSummary.tone}`}>
                  {lastActionSummary.label}
                </div>
                <details open>
                  <summary style={{ cursor: "pointer" }}>JSON Response</summary>
                  <pre>{JSON.stringify(actionOutput, null, 2)}</pre>
                </details>
              </>
            )}
          </article>
        </section>
      )}

      {/* ── Source Intelligence (unified — replaces separate "Connector */}
      {/*    Diagnostics" and "Per-Source Check" sections) ─────────────── */}
      {(sourceCheck || connectorDiag?.connectors?.length > 0) && (
        <section className="grid">
          <article className="card">
            <h2>Source Intelligence</h2>

            {sourceCheck
              ? (() => {
                  const checks = sourceCheck.source_checks || [];
                  const grouped = {};
                  for (const s of checks) {
                    const key = s.connector || "unknown";
                    if (!grouped[key]) grouped[key] = [];
                    grouped[key].push(s);
                  }
                  const connectors = Object.keys(grouped).sort();
                  return (
                    <>
                      <div className="source-intel-summary">
                        <span className="chip chip-ok">
                          {sourceCheck.working_sources}/{sourceCheck.total_sources} working
                        </span>
                        <span className="chip">{sourceCheck.raw_item_count || 0} items</span>
                        <span className="chip">{connectors.length} connectors</span>
                      </div>
                      <div className="connector-diag-grid">
                        {connectors.map((conn) => {
                          const sources = grouped[conn];
                          const totalFetched = sources.reduce(
                            (a, s) => a + (s.fetched_count || 0),
                            0
                          );
                          const totalMatched = sources.reduce(
                            (a, s) => a + (s.matched_count || 0),
                            0
                          );
                          const failedCount = sources.filter(
                            (s) => s.status === "failed"
                          ).length;
                          return (
                            <details
                              key={conn}
                              className="connector-diag-card"
                              open={failedCount > 0 || totalMatched > 0}
                            >
                              <summary>
                                <strong>{conn}</strong>
                                <span className="chip-row" style={{ marginLeft: "0.5rem" }}>
                                  <span className="chip chip-ok">
                                    {sources.length} sources
                                  </span>
                                  <span className="chip chip-ok">{totalFetched} fetched</span>
                                  {totalMatched > 0 && (
                                    <span className="chip chip-warn">
                                      {totalMatched} matched
                                    </span>
                                  )}
                                  {failedCount > 0 && (
                                    <span className="chip chip-error">
                                      {failedCount} failed
                                    </span>
                                  )}
                                </span>
                              </summary>
                              <table
                                className="table"
                                style={{ marginTop: "0.5rem", fontSize: "0.85rem" }}
                              >
                                <thead>
                                  <tr>
                                    <th>Source</th>
                                    <th>Status</th>
                                    <th>Freshness</th>
                                    <th>Fetched</th>
                                    <th>Matched</th>
                                    <th>Match Reasons</th>
                                    <th>Latest Published</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {sources.map((s) => (
                                    <tr
                                      key={`${s.source_name}-${s.source_url}`}
                                      style={
                                        s.status === "failed"
                                          ? { color: "#ff6565" }
                                          : undefined
                                      }
                                    >
                                      <td title={s.source_url}>{s.source_name}</td>
                                      <td>
                                        {s.status}
                                        {s.stale_action ? ` (${s.stale_action})` : ""}
                                      </td>
                                      <td>
                                        <span
                                          className={`chip chip-${freshnessTone(
                                            s.freshness_status
                                          )}`}
                                        >
                                          {s.freshness_status}
                                        </span>
                                      </td>
                                      <td>{fmtNumber(s.fetched_count, 0)}</td>
                                      <td>{fmtNumber(s.matched_count, 0)}</td>
                                      <td>{formatMatchReasons(s.match_reasons)}</td>
                                      <td>
                                        {s.latest_published_at || "-"}
                                        {s.latest_age_days !== null &&
                                        s.latest_age_days !== undefined
                                          ? ` (${fmtNumber(s.latest_age_days, 1)}d)`
                                          : ""}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </details>
                          );
                        })}
                      </div>
                    </>
                  );
                })()
              : connectorDiag?.connectors?.length > 0
              ? (
                <>
                  <div className="source-intel-summary">
                    <span className="chip">
                      {connectorDiag.total_fetched || 0} items fetched
                    </span>
                  </div>
                  <div className="connector-diag-grid">
                    {connectorDiag.connectors.map((c) => (
                      <details key={c.connector} className="connector-diag-card">
                        <summary>
                          <strong>{c.connector}</strong>
                          <span className="chip-row" style={{ marginLeft: "0.5rem" }}>
                            <span className="chip chip-ok">{c.fetched} fetched</span>
                            <span className="chip chip-warn">{c.matched} matched</span>
                            {c.failed > 0 && (
                              <span className="chip chip-error">{c.failed} failed</span>
                            )}
                          </span>
                        </summary>
                        {c.errors?.length > 0 && (
                          <div
                            className="error"
                            style={{ margin: "0.5rem 0", fontSize: "0.8rem" }}
                          >
                            {c.errors.map((e, i) => (
                              <div key={i}>{e}</div>
                            ))}
                          </div>
                        )}
                        {c.warnings?.length > 0 && (
                          <div
                            style={{
                              margin: "0.25rem 0",
                              fontSize: "0.8rem",
                              color: "#f0c674",
                            }}
                          >
                            {c.warnings.map((w, i) => (
                              <div key={i}>\u26A0 {w}</div>
                            ))}
                          </div>
                        )}
                        <table
                          className="table"
                          style={{ marginTop: "0.5rem", fontSize: "0.85rem" }}
                        >
                          <thead>
                            <tr>
                              <th>Source</th>
                              <th>Status</th>
                              <th>Fetched</th>
                              <th>Matched</th>
                              <th>Freshness</th>
                              <th>Match Reasons</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(c.sources || []).map((s, i) => (
                              <tr
                                key={i}
                                style={
                                  s.status === "failed" ? { color: "#ff6565" } : undefined
                                }
                              >
                                <td title={s.url}>{s.name}</td>
                                <td>{s.status}</td>
                                <td>{s.fetched}</td>
                                <td>{s.matched}</td>
                                <td>
                                  <span
                                    className={`chip chip-${freshnessTone(s.freshness)}`}
                                  >
                                    {s.freshness}
                                  </span>
                                </td>
                                <td>{formatMatchReasons(s.match_reasons)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </details>
                    ))}
                  </div>
                </>
              )
              : null}
          </article>
        </section>
      )}

      {/* ── Report Quality Workbench ────────────────────────────── */}
      <section className="grid two">
        <article className="card">
          <h2>Report Quality Workbench</h2>
          {!workbench ? (
            <div className="muted">
              Run &quot;AI vs Deterministic&quot; to populate side-by-side quality diagnostics.
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Deterministic</th>
                  <th>AI</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Status</td>
                  <td>{workbench?.deterministic?.report_quality?.status || "-"}</td>
                  <td>{workbench?.ai?.report_quality?.status || "-"}</td>
                </tr>
                <tr>
                  <td>Citation Density</td>
                  <td>
                    {fmtNumber(
                      workbench?.deterministic?.report_quality?.metrics?.citation_density
                    )}
                  </td>
                  <td>
                    {fmtNumber(workbench?.ai?.report_quality?.metrics?.citation_density)}
                  </td>
                </tr>
                <tr>
                  <td>Word Count</td>
                  <td>
                    {fmtNumber(
                      workbench?.deterministic?.report_quality?.metrics?.word_count,
                      0
                    )}
                  </td>
                  <td>
                    {fmtNumber(workbench?.ai?.report_quality?.metrics?.word_count, 0)}
                  </td>
                </tr>
                <tr>
                  <td>Missing Sections</td>
                  <td>
                    {(
                      workbench?.deterministic?.report_quality?.metrics?.missing_sections ||
                      []
                    ).length}
                  </td>
                  <td>
                    {(
                      workbench?.ai?.report_quality?.metrics?.missing_sections || []
                    ).length}
                  </td>
                </tr>
                <tr>
                  <td>Unsupported Incident Blocks</td>
                  <td>
                    {(
                      workbench?.deterministic?.report_quality?.metrics
                        ?.unsupported_incident_blocks || []
                    ).length}
                  </td>
                  <td>
                    {(
                      workbench?.ai?.report_quality?.metrics
                        ?.unsupported_incident_blocks || []
                    ).length}
                  </td>
                </tr>
                <tr>
                  <td>Invalid Citation Refs</td>
                  <td>
                    {(
                      workbench?.deterministic?.report_quality?.metrics
                        ?.invalid_citation_refs || []
                    ).length}
                  </td>
                  <td>
                    {(
                      workbench?.ai?.report_quality?.metrics?.invalid_citation_refs || []
                    ).length}
                  </td>
                </tr>
              </tbody>
            </table>
          )}
        </article>

        <article className="card">
          <h2>Section Budget Usage</h2>
          {!workbench ? (
            <div className="muted">No workbench run yet.</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Section</th>
                  <th>Limit</th>
                  <th>Det</th>
                  <th>AI</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ["executive_summary", "executive_summary_max_words"],
                  ["source_reliability", "source_reliability_max_words"],
                  ["risk_outlook", "risk_outlook_max_words"],
                  ["method", "method_max_words"],
                ].map(([sectionKey, limitKey]) => {
                  const sectionTitle =
                    workbench?.template?.sections?.[sectionKey] ||
                    sectionKey.replaceAll("_", " ");
                  return (
                    <tr key={sectionKey}>
                      <td>{sectionTitle}</td>
                      <td>{fmtNumber(workbench?.template?.limits?.[limitKey], 0)}</td>
                      <td>
                        {fmtNumber(
                          workbench?.deterministic?.section_word_usage?.[sectionTitle],
                          0
                        )}
                      </td>
                      <td>
                        {fmtNumber(
                          workbench?.ai?.section_word_usage?.[sectionTitle],
                          0
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </article>
      </section>

      {/* ── Workbench Markdown (only when data exists) ──────────── */}
      {workbench && (
        <section className="grid two">
          <article className="card">
            <h2>Deterministic Markdown</h2>
            <pre>{workbench?.deterministic?.markdown || "No output."}</pre>
          </article>
          <article className="card">
            <h2>AI Markdown</h2>
            <pre>{workbench?.ai?.markdown || "No output."}</pre>
          </article>
        </section>
      )}

      {/* ── Situation Analysis Output (conditional) ─────────────── */}
      {saOutput?.markdown && (
        <section className="grid">
          <article className="card">
            <h2>Situation Analysis</h2>
            <div className="timing-line">{saOutput.output_file || ""}</div>
            <pre style={{ whiteSpace: "pre-wrap", maxHeight: "60vh", overflow: "auto" }}>
              {saOutput.markdown}
            </pre>
          </article>
        </section>
      )}

      {/* ── Generated Reports ───────────────────────────────────── */}
      <section className="grid two">
        <article className="card">
          <h2>Generated Reports</h2>
          <ul className="report-list">
            {reports.map((r) => (
              <li key={r.name}>
                <button className="link" onClick={() => void fetchReport(r.name)}>
                  {r.name}
                </button>
              </li>
            ))}
          </ul>
        </article>
        <article className="card">
          <h2>Report Preview</h2>
          <pre>{selectedReport?.markdown || "Select a report to preview."}</pre>
        </article>
      </section>
    </main>
  );
}
