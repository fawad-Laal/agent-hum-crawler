import { useEffect, useMemo, useState } from "react";

const defaultForm = {
  countries: "Madagascar,Mozambique",
  disaster_types: "cyclone/storm,flood",
  max_age_days: 30,
  limit: 10,
  limit_cycles: 20,
  limit_events: 30,
  country_min_events: 1,
  max_per_connector: 8,
  max_per_source: 4,
  report_template: "config/report_template.brief.json",
  use_llm: false,
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

  useEffect(() => {
    void fetchOverview().catch((e) => setError(String(e)));
    void fetchReports().catch((e) => setError(String(e)));
    void fetchWorkbenchProfiles().catch((e) => setError(String(e)));
  }, []);

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

  return (
    <main className="page">
      <header className="top">
        <div>
          <h1>Agent HUM Crawler Dashboard</h1>
          <p>Phase 1: Monitoring trends, hardening thresholds, conformance, and source hotspots.</p>
        </div>
        <button className="ghost" onClick={() => void fetchOverview()}>
          Refresh
        </button>
      </header>

      {error ? <div className="error">{error}</div> : null}

      <section className="grid kpis">
        <article className="card kpi">
          <div className="kpi-label">Cycles Analyzed</div>
          <div className="kpi-value">{fmtNumber(quality.cycles_analyzed, 0)}</div>
        </article>
        <article className="card kpi">
          <div className="kpi-label">Events Analyzed</div>
          <div className="kpi-value">{fmtNumber(quality.events_analyzed, 0)}</div>
        </article>
        <article className="card kpi">
          <div className="kpi-label">Duplicate Rate</div>
          <div className="kpi-value">{fmtNumber(quality.duplicate_rate_estimate)}</div>
        </article>
        <article className="card kpi">
          <div className="kpi-label">Traceable Rate</div>
          <div className="kpi-value">{fmtNumber(quality.traceable_rate)}</div>
        </article>
        <article className="card kpi">
          <div className="kpi-label">Hardening</div>
          <div className={`kpi-value status-${hardening.status || "unknown"}`}>{hardening.status || "-"}</div>
        </article>
      </section>

      <section className="grid two">
        <article className="card">
          <h2>Cycle Trends</h2>
          <div className="trend">
            <div>
              <div className="metric-label">Events per Cycle</div>
              <TinyLineChart values={trend.events} color="#63b3ff" />
            </div>
            <div>
              <div className="metric-label">LLM Enriched per Cycle</div>
              <TinyLineChart values={trend.llmEnriched} color="#1ec97e" />
            </div>
            <div>
              <div className="metric-label">LLM Fallback per Cycle</div>
              <TinyLineChart values={trend.llmFallback} color="#f4c542" />
            </div>
            <div>
              <div className="metric-label">LLM Validation Failures</div>
              <TinyLineChart values={trend.llmValidationFails} color="#ff6565" />
            </div>
          </div>
        </article>

        <article className="card">
          <h2>Quality Rate Trends</h2>
          <div className="trend">
            <div>
              <div className="metric-label">Duplicate Rate (rolling)</div>
              <TinyLineChart values={qualityRateTrend.duplicate} color="#ff6565" yMax={1} />
            </div>
            <div>
              <div className="metric-label">Traceable Rate (rolling)</div>
              <TinyLineChart values={qualityRateTrend.traceable} color="#57e58e" yMax={1} />
            </div>
            <div>
              <div className="metric-label">LLM Enrichment Rate</div>
              <TinyLineChart values={qualityRateTrend.llmEnrichment} color="#f4c542" yMax={1} />
            </div>
            <div>
              <div className="metric-label">Citation Coverage Rate</div>
              <TinyLineChart values={qualityRateTrend.citationCoverage} color="#63b3ff" yMax={1} />
            </div>
          </div>
        </article>
      </section>

      <section className="grid two">
        <article className="card">
          <h2>Hardening Thresholds</h2>
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
        </article>
        <article className="card">
          <h2>Conformance and Security Snapshot</h2>
          <div className="kv">
            <div>Latest E2E Status</div>
            <div>{e2e.status || "-"}</div>
            <div>Conformance Status</div>
            <div>{e2e?.checks?.conformance_status || "-"}</div>
            <div>Security Status</div>
            <div>{e2e?.checks?.security_status || "-"}</div>
            <div>Report Quality Status</div>
            <div>{e2e?.checks?.report_quality_status || "-"}</div>
            <div>Hardening Status</div>
            <div>{e2e?.checks?.hardening_status || "-"}</div>
            <div>Artifact Directory</div>
            <div className="truncate">{e2e.artifacts_dir || "-"}</div>
          </div>
        </article>

        <article className="card">
          <h2>Feature Flags</h2>
          <div className="kv">
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
        </article>

        <article className="card">
          <h2>Source Health Hotspots</h2>
          <table className="table">
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
        </article>
      </section>

      <section className="grid two">
        <article className="card">
          <h2>Operator Controls</h2>
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
                onChange={(e) => setForm((s) => ({ ...s, max_age_days: Number(e.target.value) }))}
              />
            </label>
            <label>
              Limit Cycles
              <input
                type="number"
                value={form.limit_cycles}
                onChange={(e) => setForm((s) => ({ ...s, limit_cycles: Number(e.target.value) }))}
              />
            </label>
            <label>
              Limit Events
              <input
                type="number"
                value={form.limit_events}
                onChange={(e) => setForm((s) => ({ ...s, limit_events: Number(e.target.value) }))}
              />
            </label>
          </div>
          <div className="row">
            <label>
              Country Min Events
              <input
                type="number"
                value={form.country_min_events}
                onChange={(e) => setForm((s) => ({ ...s, country_min_events: Number(e.target.value) }))}
              />
            </label>
            <label>
              Max / Connector
              <input
                type="number"
                value={form.max_per_connector}
                onChange={(e) => setForm((s) => ({ ...s, max_per_connector: Number(e.target.value) }))}
              />
            </label>
            <label>
              Max / Source
              <input
                type="number"
                value={form.max_per_source}
                onChange={(e) => setForm((s) => ({ ...s, max_per_source: Number(e.target.value) }))}
              />
            </label>
          </div>
          <label>
            Template
            <select
              value={form.report_template}
              onChange={(e) => setForm((s) => ({ ...s, report_template: e.target.value }))}
            >
              <option value="config/report_template.brief.json">Brief</option>
              <option value="config/report_template.detailed.json">Detailed</option>
              <option value="config/report_template.json">Default</option>
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
          <label>
            Saved Compare Presets
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
              <option value="">Select preset...</option>
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
                Save Preset
              </button>
              <button type="button" className="ghost" disabled={!selectedPreset} onClick={() => void handleDeletePreset()}>
                Delete Preset
              </button>
            </div>
          </div>
          <div className="actions">
            <button disabled={busy} onClick={() => void handleRunCycle()}>
              {busy ? "Running..." : "Run Cycle"}
            </button>
            <button disabled={busy} className="ghost" onClick={() => void handleSourceCheck()}>
              {busy ? "Checking..." : "Source Check"}
            </button>
            <button disabled={busy} className="accent" onClick={() => void handleWriteReport()}>
              {busy ? "Working..." : "Write Report"}
            </button>
            <button disabled={workbenchBusy} onClick={() => void handleRunWorkbench()}>
              {workbenchBusy ? "Comparing..." : "Compare AI vs Deterministic"}
            </button>
            <button disabled={workbenchBusy} className="ghost" onClick={() => void handleRerunLastProfile()}>
              {workbenchBusy ? "Running..." : "Rerun Last Profile"}
            </button>
          </div>
        </article>

        <article className="card">
          <h2>Last Action Output</h2>
          <div className={`status-inline status-${lastActionSummary.tone}`}>Status: {lastActionSummary.label}</div>
          <pre>{JSON.stringify(actionOutput, null, 2)}</pre>
        </article>
      </section>

      <section className="grid">
        <article className="card">
          <h2>Per-Source Check</h2>
          {!sourceCheck ? (
            <div className="muted">Run Source Check to verify each feed one-by-one.</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Connector</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Freshness</th>
                  <th>Stale Action</th>
                  <th>Fetched</th>
                  <th>Matched</th>
                  <th>Match Reasons</th>
                  <th>Latest Published</th>
                  <th>Working</th>
                </tr>
              </thead>
              <tbody>
                {(sourceCheck.source_checks || []).map((s) => (
                  <tr key={`${s.connector}-${s.source_name}-${s.source_url}`}>
                    <td>{s.connector}</td>
                    <td title={s.source_url}>{s.source_name}</td>
                    <td>{s.status}</td>
                    <td>
                      <span className={`chip chip-${freshnessTone(s.freshness_status)}`}>
                        {s.freshness_status}
                      </span>
                    </td>
                    <td>{s.stale_action || "-"}</td>
                    <td>{fmtNumber(s.fetched_count, 0)}</td>
                    <td>{fmtNumber(s.matched_count, 0)}</td>
                    <td>{formatMatchReasons(s.match_reasons)}</td>
                    <td>
                      {s.latest_published_at || "-"}
                      {s.latest_age_days !== null && s.latest_age_days !== undefined ? ` (${fmtNumber(s.latest_age_days, 1)}d)` : ""}
                    </td>
                    <td>
                      <input type="checkbox" checked={Boolean(s.working)} readOnly />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </article>
      </section>

      <section className="grid two">
        <article className="card">
          <h2>Report Quality Workbench (Phase 2)</h2>
          {!workbench ? (
            <div className="muted">
              Run "Compare AI vs Deterministic" to populate side-by-side quality diagnostics.
            </div>
          ) : (
            <>
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
                    <td>{fmtNumber(workbench?.deterministic?.report_quality?.metrics?.citation_density)}</td>
                    <td>{fmtNumber(workbench?.ai?.report_quality?.metrics?.citation_density)}</td>
                  </tr>
                  <tr>
                    <td>Word Count</td>
                    <td>{fmtNumber(workbench?.deterministic?.report_quality?.metrics?.word_count, 0)}</td>
                    <td>{fmtNumber(workbench?.ai?.report_quality?.metrics?.word_count, 0)}</td>
                  </tr>
                  <tr>
                    <td>Missing Sections</td>
                    <td>{(workbench?.deterministic?.report_quality?.metrics?.missing_sections || []).length}</td>
                    <td>{(workbench?.ai?.report_quality?.metrics?.missing_sections || []).length}</td>
                  </tr>
                  <tr>
                    <td>Unsupported Incident Blocks</td>
                    <td>
                      {(workbench?.deterministic?.report_quality?.metrics?.unsupported_incident_blocks || [])
                        .length}
                    </td>
                    <td>
                      {(workbench?.ai?.report_quality?.metrics?.unsupported_incident_blocks || []).length}
                    </td>
                  </tr>
                  <tr>
                    <td>Invalid Citation Refs</td>
                    <td>{(workbench?.deterministic?.report_quality?.metrics?.invalid_citation_refs || []).length}</td>
                    <td>{(workbench?.ai?.report_quality?.metrics?.invalid_citation_refs || []).length}</td>
                  </tr>
                </tbody>
              </table>
            </>
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
                    workbench?.template?.sections?.[sectionKey] || sectionKey.replaceAll("_", " ");
                  return (
                    <tr key={sectionKey}>
                      <td>{sectionTitle}</td>
                      <td>{fmtNumber(workbench?.template?.limits?.[limitKey], 0)}</td>
                      <td>{fmtNumber(workbench?.deterministic?.section_word_usage?.[sectionTitle], 0)}</td>
                      <td>{fmtNumber(workbench?.ai?.section_word_usage?.[sectionTitle], 0)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </article>
      </section>

      <section className="grid two">
        <article className="card">
          <h2>Deterministic Markdown</h2>
          <pre>{workbench?.deterministic?.markdown || "No workbench output yet."}</pre>
        </article>
        <article className="card">
          <h2>AI Markdown</h2>
          <pre>{workbench?.ai?.markdown || "No workbench output yet."}</pre>
        </article>
      </section>

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
          <pre>{selectedReport?.markdown || "Select a report to preview markdown."}</pre>
        </article>
      </section>
    </main>
  );
}
