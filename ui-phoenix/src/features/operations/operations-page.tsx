/**
 * Project Phoenix — Phase 3 Operations Page
 * Command Center: collection form, hazard picker, cycle runner,
 * report writer, source check, SA writer, and full pipeline.
 * All actions use existing mutation hooks with toast feedback.
 */

import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Collapsible } from "@/components/ui/collapsible";
import { CountrySelect } from "@/components/operations/country-select";
import { HazardPicker } from "@/components/operations/hazard-picker";
import { useFormStore } from "@/stores/form-store";
import {
  useRunCycle,
  useWriteReport,
  useRunSourceCheck,
  useWriteSA,
  useRunPipeline,
} from "@/hooks/use-mutations";
import { toast } from "sonner";
import {
  Radio,
  Play,
  FileText,
  Search,
  FileBarChart,
  Rocket,
  Loader2,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import { useState, useCallback } from "react";
import type { SourceCheckResponse, SAResponse } from "@/types";

// ── Result display components ───────────────────────────────

function CliResultDisplay({ status, output, error }: { status: string; output?: string; error?: string }) {
  return (
    <div className="mt-4 rounded-lg bg-background/80 border border-border p-4 text-sm">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Result
        </span>
        <Badge variant={status === "ok" || status === "pass" ? "success" : "destructive"}>
          {status}
        </Badge>
      </div>
      {output && (
        <pre className="mt-2 max-h-60 overflow-auto whitespace-pre-wrap text-xs text-muted-foreground font-mono">
          {output}
        </pre>
      )}
      {error && (
        <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs text-destructive font-mono">
          {error}
        </pre>
      )}
    </div>
  );
}

function SourceCheckDisplay({ data }: { data: SourceCheckResponse }) {
  return (
    <div className="mt-4 rounded-lg bg-background/80 border border-border p-4">
      <div className="flex items-center gap-3 mb-3">
        <Badge variant="success">{data.working_sources} working</Badge>
        <Badge variant="outline">{data.total_sources} total</Badge>
        <Badge variant="secondary">{data.raw_item_count} raw items</Badge>
      </div>
      <div className="max-h-64 overflow-auto space-y-1">
        {data.source_checks.map((src) => (
          <div
            key={`${src.connector}-${src.source_name}`}
            className="flex items-center justify-between rounded-md px-3 py-1.5 text-sm bg-muted/20"
          >
            <div className="flex items-center gap-2">
              <span
                className={`h-2 w-2 rounded-full ${src.working ? "bg-status-pass" : "bg-status-fail"}`}
              />
              <span className="text-foreground/90">{src.source_name}</span>
              <span className="text-xs text-muted-foreground">({src.connector})</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>{src.fetched_count} fetched</span>
              <span>{src.matched_count} matched</span>
              <Badge
                variant={
                  src.freshness_status === "fresh"
                    ? "success"
                    : src.freshness_status === "stale"
                      ? "warning"
                      : "outline"
                }
                className="text-[10px]"
              >
                {src.freshness_status}
              </Badge>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function SAResultDisplay({ data }: { data: SAResponse }) {
  return (
    <div className="mt-4 rounded-lg bg-background/80 border border-border p-4">
      <div className="flex items-center gap-2 mb-2">
        <Badge variant="success">Generated</Badge>
        <span className="text-xs text-muted-foreground">{data.output_file}</span>
      </div>
      {data.quality_gate && data.quality_gate.length > 0 && (
        <div className="mt-3 space-y-1.5">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Quality Gate
          </span>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {data.quality_gate.map((dim) => (
              <div
                key={dim.dimension}
                className="rounded-md bg-muted/30 px-3 py-2 text-sm"
              >
                <span className="text-foreground/80">{dim.label}</span>
                <div className="mt-1 font-mono text-xs text-muted-foreground">
                  {dim.score}/{dim.max}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      <details className="mt-3">
        <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground transition-colors">
          Preview markdown
        </summary>
        <pre className="mt-2 max-h-60 overflow-auto whitespace-pre-wrap text-xs text-muted-foreground font-mono">
          {data.markdown.slice(0, 3000)}
          {data.markdown.length > 3000 ? "\n…(truncated)" : ""}
        </pre>
      </details>
    </div>
  );
}

// ── Main Page ───────────────────────────────────────────────

export function OperationsPage() {
  const { form, setField, resetForm } = useFormStore();

  // Mutations
  const runCycle = useRunCycle();
  const writeReport = useWriteReport();
  const sourceCheck = useRunSourceCheck();
  const writeSA = useWriteSA();
  const runPipeline = useRunPipeline();

  // Local state for last action results
  const [lastAction, setLastAction] = useState<string | null>(null);
  const [cliResult, setCliResult] = useState<{ status: string; output?: string; error?: string } | null>(null);
  const [sourceCheckResult, setSourceCheckResult] = useState<SourceCheckResponse | null>(null);
  const [saResult, setSAResult] = useState<SAResponse | null>(null);

  const anyRunning =
    runCycle.isPending ||
    writeReport.isPending ||
    sourceCheck.isPending ||
    writeSA.isPending ||
    runPipeline.isPending;

  // ── Action handlers ─────────────────────────────────────

  const handleRunCycle = useCallback(() => {
    setLastAction("cycle");
    setCliResult(null);
    setSourceCheckResult(null);
    setSAResult(null);
    runCycle.mutate(
      {
        countries: form.countries,
        disaster_types: form.disaster_types,
        limit: form.limit,
        max_age_days: form.max_age_days,
      },
      {
        onSuccess: (data) => {
          setCliResult(data);
          toast.success("Collection cycle completed", {
            description: `Status: ${data.status}`,
          });
        },
        onError: (err) => {
          setCliResult({ status: "error", error: err.message });
          toast.error("Cycle failed", { description: err.message });
        },
      }
    );
  }, [form, runCycle]);

  const handleWriteReport = useCallback(() => {
    setLastAction("report");
    setCliResult(null);
    setSourceCheckResult(null);
    setSAResult(null);
    writeReport.mutate(
      {
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
      },
      {
        onSuccess: (data) => {
          setCliResult(data);
          toast.success("Report generated", {
            description: `Status: ${data.status}`,
          });
        },
        onError: (err) => {
          setCliResult({ status: "error", error: err.message });
          toast.error("Report failed", { description: err.message });
        },
      }
    );
  }, [form, writeReport]);

  const handleSourceCheck = useCallback(() => {
    setLastAction("source-check");
    setCliResult(null);
    setSourceCheckResult(null);
    setSAResult(null);
    sourceCheck.mutate(
      {
        countries: form.countries,
        disaster_types: form.disaster_types,
        limit: form.limit,
        max_age_days: form.max_age_days,
      },
      {
        onSuccess: (data) => {
          setSourceCheckResult(data);
          toast.success("Source check completed", {
            description: `${data.working_sources}/${data.total_sources} sources working`,
          });
        },
        onError: (err) => {
          setCliResult({ status: "error", error: err.message });
          toast.error("Source check failed", { description: err.message });
        },
      }
    );
  }, [form, sourceCheck]);

  const handleWriteSA = useCallback(() => {
    setLastAction("sa");
    setCliResult(null);
    setSourceCheckResult(null);
    setSAResult(null);
    writeSA.mutate(
      {
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
        quality_gate: form.sa_quality_gate,
      },
      {
        onSuccess: (data) => {
          setSAResult(data);
          toast.success("Situation Analysis generated", {
            description: `Output: ${data.output_file}`,
          });
        },
        onError: (err) => {
          setCliResult({ status: "error", error: err.message });
          toast.error("SA generation failed", { description: err.message });
        },
      }
    );
  }, [form, writeSA]);

  const handleRunPipeline = useCallback(() => {
    setLastAction("pipeline");
    setCliResult(null);
    setSourceCheckResult(null);
    setSAResult(null);
    runPipeline.mutate(
      {
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
      },
      {
        onSuccess: (data) => {
          setCliResult(data);
          toast.success("Full pipeline completed", {
            description: `Status: ${data.status}`,
          });
        },
        onError: (err) => {
          setCliResult({ status: "error", error: err.message });
          toast.error("Pipeline failed", { description: err.message });
        },
      }
    );
  }, [form, runPipeline]);

  // ── Render ──────────────────────────────────────────────

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Radio className="h-5 w-5 text-primary" />
          <h1 className="text-xl font-semibold">Command Center</h1>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={resetForm}
          className="gap-1.5"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Reset
        </Button>
      </div>

      {/* ── Collection Parameters ──────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>Collection Parameters</CardTitle>
          <CardDescription>
            Configure target countries, hazard types, and retrieval limits
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Countries */}
          <div className="space-y-2">
            <Label>Target Countries</Label>
            <CountrySelect
              value={form.countries}
              onChange={(v) => setField("countries", v)}
            />
          </div>

          {/* Hazard Types */}
          <div className="space-y-2">
            <Label>Hazard Types</Label>
            <HazardPicker
              value={form.disaster_types}
              onChange={(v) => setField("disaster_types", v)}
            />
          </div>

          <Separator />

          {/* Numeric Parameters Grid */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            <div className="space-y-1.5">
              <Label htmlFor="max_age_days">Max Age (days)</Label>
              <Input
                id="max_age_days"
                type="number"
                min={1}
                value={form.max_age_days}
                onChange={(e) => setField("max_age_days", Number(e.target.value))}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="limit">Item Limit</Label>
              <Input
                id="limit"
                type="number"
                min={1}
                value={form.limit}
                onChange={(e) => setField("limit", Number(e.target.value))}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="limit_cycles">Cycle Limit</Label>
              <Input
                id="limit_cycles"
                type="number"
                min={1}
                value={form.limit_cycles}
                onChange={(e) => setField("limit_cycles", Number(e.target.value))}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="limit_events">Event Limit</Label>
              <Input
                id="limit_events"
                type="number"
                min={1}
                value={form.limit_events}
                onChange={(e) => setField("limit_events", Number(e.target.value))}
              />
            </div>
          </div>

          {/* Retrieval Tuning */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label htmlFor="country_min_events">Country Min Events</Label>
              <Input
                id="country_min_events"
                type="number"
                min={0}
                value={form.country_min_events}
                onChange={(e) => setField("country_min_events", Number(e.target.value))}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="max_per_connector">Max / Connector</Label>
              <Input
                id="max_per_connector"
                type="number"
                min={1}
                value={form.max_per_connector}
                onChange={(e) => setField("max_per_connector", Number(e.target.value))}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="max_per_source">Max / Source</Label>
              <Input
                id="max_per_source"
                type="number"
                min={1}
                value={form.max_per_source}
                onChange={(e) => setField("max_per_source", Number(e.target.value))}
              />
            </div>
          </div>

          <Separator />

          {/* Toggles row */}
          <div className="flex flex-wrap items-center gap-6">
            <div className="flex items-center gap-3">
              <Switch
                checked={form.use_llm}
                onCheckedChange={(v) => setField("use_llm", v)}
              />
              <Label className="flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-primary" />
                AI Enrichment
              </Label>
            </div>
            <div className="space-y-1.5 flex items-center gap-3">
              <Label htmlFor="report_template" className="whitespace-nowrap">Report Template</Label>
              <Input
                id="report_template"
                value={form.report_template}
                onChange={(e) => setField("report_template", e.target.value)}
                className="w-64"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ── SA Parameters (Collapsible) ────────────────────── */}
      <Card>
        <Collapsible
          trigger={
            <span className="flex items-center gap-2 text-base font-semibold">
              <FileBarChart className="h-4 w-4 text-primary" />
              Situation Analysis Parameters
            </span>
          }
        >
          <div className="space-y-4 pb-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="sa_title">SA Title</Label>
                <Input
                  id="sa_title"
                  value={form.sa_title}
                  onChange={(e) => setField("sa_title", e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sa_event_name">Event Name</Label>
                <Input
                  id="sa_event_name"
                  value={form.sa_event_name}
                  onChange={(e) => setField("sa_event_name", e.target.value)}
                  placeholder="Auto-detect if blank"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sa_event_type">Event Type</Label>
                <Input
                  id="sa_event_type"
                  value={form.sa_event_type}
                  onChange={(e) => setField("sa_event_type", e.target.value)}
                  placeholder="Auto-detect if blank"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sa_period">Period</Label>
                <Input
                  id="sa_period"
                  value={form.sa_period}
                  onChange={(e) => setField("sa_period", e.target.value)}
                  placeholder="e.g. February 2026"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="sa_template">SA Template</Label>
                <Input
                  id="sa_template"
                  value={form.sa_template}
                  onChange={(e) => setField("sa_template", e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sa_limit_events">SA Event Limit</Label>
                <Input
                  id="sa_limit_events"
                  type="number"
                  min={1}
                  value={form.sa_limit_events}
                  onChange={(e) => setField("sa_limit_events", Number(e.target.value))}
                />
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Switch
                checked={form.sa_quality_gate}
                onCheckedChange={(v) => setField("sa_quality_gate", v)}
              />
              <Label>Enable Quality Gate</Label>
            </div>
          </div>
        </Collapsible>
      </Card>

      {/* ── Pipeline Parameters (Collapsible) ──────────────── */}
      <Card>
        <Collapsible
          trigger={
            <span className="flex items-center gap-2 text-base font-semibold">
              <Rocket className="h-4 w-4 text-primary" />
              Full Pipeline Parameters
            </span>
          }
        >
          <div className="space-y-4 pb-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="pipeline_report_title">Report Title</Label>
                <Input
                  id="pipeline_report_title"
                  value={form.pipeline_report_title}
                  onChange={(e) => setField("pipeline_report_title", e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="pipeline_sa_title">SA Title</Label>
                <Input
                  id="pipeline_sa_title"
                  value={form.pipeline_sa_title}
                  onChange={(e) => setField("pipeline_sa_title", e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="pipeline_event_name">Event Name</Label>
                <Input
                  id="pipeline_event_name"
                  value={form.pipeline_event_name}
                  onChange={(e) => setField("pipeline_event_name", e.target.value)}
                  placeholder="Auto-detect if blank"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="pipeline_event_type">Event Type</Label>
                <Input
                  id="pipeline_event_type"
                  value={form.pipeline_event_type}
                  onChange={(e) => setField("pipeline_event_type", e.target.value)}
                  placeholder="Auto-detect if blank"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="pipeline_period">Period</Label>
                <Input
                  id="pipeline_period"
                  value={form.pipeline_period}
                  onChange={(e) => setField("pipeline_period", e.target.value)}
                  placeholder="e.g. February 2026"
                />
              </div>
            </div>
          </div>
        </Collapsible>
      </Card>

      {/* ── Action Buttons ─────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>Actions</CardTitle>
          <CardDescription>
            Execute collection, reporting, and analysis operations
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Button
              onClick={handleRunCycle}
              disabled={anyRunning}
              className="gap-2"
            >
              {runCycle.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Run Cycle
            </Button>

            <Button
              variant="secondary"
              onClick={handleWriteReport}
              disabled={anyRunning}
              className="gap-2"
            >
              {writeReport.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FileText className="h-4 w-4" />
              )}
              Write Report
            </Button>

            <Button
              variant="outline"
              onClick={handleSourceCheck}
              disabled={anyRunning}
              className="gap-2"
            >
              {sourceCheck.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
              Source Check
            </Button>

            <Button
              variant="secondary"
              onClick={handleWriteSA}
              disabled={anyRunning}
              className="gap-2"
            >
              {writeSA.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FileBarChart className="h-4 w-4" />
              )}
              Write SA
            </Button>

            <Separator orientation="vertical" className="h-10" />

            <Button
              variant="destructive"
              onClick={handleRunPipeline}
              disabled={anyRunning}
              className="gap-2"
            >
              {runPipeline.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Rocket className="h-4 w-4" />
              )}
              Full Pipeline
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* ── Results Display ────────────────────────────────── */}
      {(cliResult || sourceCheckResult || saResult) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Last Action: <span className="text-primary capitalize">{lastAction}</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {lastAction === "source-check" && sourceCheckResult && (
              <SourceCheckDisplay data={sourceCheckResult} />
            )}
            {lastAction === "sa" && saResult && (
              <SAResultDisplay data={saResult} />
            )}
            {cliResult && lastAction !== "source-check" && lastAction !== "sa" && (
              <CliResultDisplay
                status={cliResult.status}
                output={cliResult.output}
                error={cliResult.error}
              />
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
