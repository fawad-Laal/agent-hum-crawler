import { useEffect, useMemo, useState } from "react";

const defaultForm = {
  countries: "Madagascar,Mozambique",
  disaster_types: "cyclone/storm,flood",
  limit: 10,
  limit_cycles: 20,
  limit_events: 30,
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

export default function App() {
  const [overview, setOverview] = useState(null);
  const [reports, setReports] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [form, setForm] = useState(defaultForm);
  const [busy, setBusy] = useState(false);
  const [actionOutput, setActionOutput] = useState(null);
  const [error, setError] = useState("");

  async function fetchOverview() {
    setError("");
    const r = await fetch("/api/overview");
    const data = await r.json();
    setOverview(data);
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

  useEffect(() => {
    void fetchOverview().catch((e) => setError(String(e)));
    void fetchReports().catch((e) => setError(String(e)));
  }, []);

  const quality = overview?.quality || {};
  const hardening = overview?.hardening || {};
  const sourceHealth = overview?.source_health || {};
  const cycles = Array.isArray(overview?.cycles) ? overview.cycles : [];
  const e2e = overview?.latest_e2e_summary || {};
  const qualityTrend = Array.isArray(overview?.quality_trend) ? overview.quality_trend : [];

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
          limit: form.limit,
        }),
      });
      const data = await r.json();
      setActionOutput(data);
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
          <div className="actions">
            <button disabled={busy} onClick={() => void handleRunCycle()}>
              Run Cycle
            </button>
            <button disabled={busy} className="accent" onClick={() => void handleWriteReport()}>
              Write Report
            </button>
          </div>
        </article>

        <article className="card">
          <h2>Last Action Output</h2>
          <pre>{JSON.stringify(actionOutput, null, 2)}</pre>
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
