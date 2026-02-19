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

function fmtNumber(v) {
  if (v === null || v === undefined) return "-";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString();
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

  const headline = useMemo(() => {
    if (!overview?.quality) return [];
    const q = overview.quality;
    const h = overview.hardening || {};
    return [
      { label: "Cycles", value: fmtNumber(q.cycles_analyzed) },
      { label: "Events", value: fmtNumber(q.events_analyzed) },
      { label: "Dup Rate", value: fmtNumber(q.duplicate_rate_estimate) },
      { label: "Traceable", value: fmtNumber(q.traceable_rate) },
      { label: "Hardening", value: h.status || "-" },
    ];
  }, [overview]);

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
          <p>Run cycles, generate reports, and track quality/hardening metrics.</p>
        </div>
        <button className="ghost" onClick={() => void fetchOverview()}>
          Refresh
        </button>
      </header>

      {error ? <div className="error">{error}</div> : null}

      <section className="grid kpis">
        {headline.map((item) => (
          <article key={item.label} className="card kpi">
            <div className="kpi-label">{item.label}</div>
            <div className="kpi-value">{item.value}</div>
          </article>
        ))}
      </section>

      <section className="grid two">
        <article className="card">
          <h2>Controls</h2>
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
          <h2>Last Action</h2>
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

