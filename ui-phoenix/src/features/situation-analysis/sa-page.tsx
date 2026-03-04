/**
 * Project Phoenix — Phase 6 Situation Analysis Page
 * SA writer with template picker, full form, quality gate chart,
 * markdown preview with TOC, and Markdown/HTML export.
 */

import { useState, useCallback, useMemo } from "react";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { MarkdownRenderer } from "@/components/ui/markdown-renderer";
import { CountrySelect } from "@/components/operations/country-select";
import { HazardPicker } from "@/components/operations/hazard-picker";
import { SAQualityGateChart } from "@/components/charts/sa-quality-gate-chart";
import { useFormStore } from "@/stores/form-store";
import { useWriteSA } from "@/hooks/use-mutations";
import { toast } from "sonner";
import {
  FlaskConical,
  Play,
  Loader2,
  Download,
  Copy,
  ChevronDown,
  ChevronRight,
  FileText,
  CheckCircle,
  XCircle,
  BookOpen,
} from "lucide-react";
import type { SAResponse } from "@/types";

// ── Template registry ─────────────────────────────────────

const SA_TEMPLATES = [
  {
    path: "config/report_template.situation_analysis.json",
    label: "OCHA Full SA",
    description: "15-section OCHA standard format (cyclone/flood crises)",
  },
  {
    path: "config/report_template.json",
    label: "Default Report",
    description: "Standard multi-section report template",
  },
  {
    path: "config/report_template.brief.json",
    label: "Brief Update",
    description: "Short donor/stakeholder update format",
  },
  {
    path: "config/report_template.detailed.json",
    label: "Detailed Brief",
    description: "Long-form analyst brief with extended sections",
  },
] as const;

// ── Section TOC extraction ────────────────────────────────

interface TocEntry {
  level: number;
  text: string;
  anchor: string;
}

function extractToc(markdown: string): TocEntry[] {
  const entries: TocEntry[] = [];
  for (const line of markdown.split("\n")) {
    const match = line.match(/^(#{1,3})\s+(.+)/);
    if (match) {
      const level = match[1].length;
      const text = match[2].trim();
      const anchor = text
        .toLowerCase()
        .replace(/[^\w\s-]/g, "")
        .replace(/\s+/g, "-");
      entries.push({ level, text, anchor });
    }
  }
  return entries;
}

// ── Export helpers ────────────────────────────────────────

function downloadMarkdown(content: string, filename: string) {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename.endsWith(".md") ? filename : `${filename}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

function exportHtml(content: string, title: string) {
  const lines = content.split("\n").map((line) => {
    const h1 = line.match(/^# (.+)/)?.[1];
    if (h1) return `<h1>${h1}</h1>`;
    const h2 = line.match(/^## (.+)/)?.[1];
    if (h2) return `<h2>${h2}</h2>`;
    const h3 = line.match(/^### (.+)/)?.[1];
    if (h3) return `<h3>${h3}</h3>`;
    if (line.trim() === "") return "<br/>";
    return `<p>${line}</p>`;
  });
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${title}</title>
  <style>
    body { font-family: Georgia, "Times New Roman", serif; max-width: 820px; margin: 60px auto; padding: 0 24px; line-height: 1.75; color: #1a1a1a; }
    h1, h2, h3 { font-family: system-ui, sans-serif; }
    h1 { font-size: 1.8rem; border-bottom: 2px solid #1a1a1a; padding-bottom: 8px; }
    h2 { font-size: 1.3rem; margin-top: 2.5em; border-bottom: 1px solid #ccc; padding-bottom: 4px; }
    h3 { font-size: 1.05rem; margin-top: 1.8em; }
    table { border-collapse: collapse; width: 100%; margin: 1.2em 0; }
    th, td { border: 1px solid #ccc; padding: 6px 12px; text-align: left; }
    th { background: #f5f5f5; }
    code { background: #f2f2f2; padding: 2px 5px; border-radius: 3px; font-size: 0.9em; }
    blockquote { border-left: 4px solid #ccc; margin: 1em 0; padding: 0.5em 1em; color: #555; }
    pre { background: #f2f2f2; padding: 12px; border-radius: 4px; overflow-x: auto; }
  </style>
</head>
<body>
${lines.join("\n")}
</body>
</html>`;
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${title.slice(0, 56).replace(/\s+/g, "-")}.html`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Template picker ───────────────────────────────────────

function TemplatePicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {SA_TEMPLATES.map((t) => {
        const active = value === t.path;
        return (
          <button
            key={t.path}
            type="button"
            onClick={() => onChange(t.path)}
            className={`rounded-lg border px-3 py-2.5 text-left text-sm transition-colors ${
              active
                ? "border-primary bg-primary/10 text-foreground"
                : "border-border bg-muted/20 text-foreground/80 hover:bg-muted/40"
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">{t.label}</span>
              {active && <CheckCircle className="h-3.5 w-3.5 shrink-0 text-primary" />}
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground">{t.description}</p>
          </button>
        );
      })}
    </div>
  );
}

// ── TOC sidebar ───────────────────────────────────────────

function TocSidebar({ entries }: { entries: TocEntry[] }) {
  if (!entries.length) return null;
  return (
    <nav className="space-y-0.5">
      {entries.map((e, i) => (
        <a
          key={`${e.anchor}-${i}`}
          href={`#${e.anchor}`}
          className={`block text-xs leading-relaxed transition-colors hover:text-foreground ${
            e.level === 1
              ? "font-semibold text-foreground/90"
              : e.level === 2
                ? "pl-3 text-muted-foreground"
                : "pl-6 text-muted-foreground/70"
          }`}
        >
          {e.text}
        </a>
      ))}
    </nav>
  );
}

// ── Output panel ──────────────────────────────────────────

function SAOutputPanel({ result }: { result: SAResponse }) {
  const toc = useMemo(() => extractToc(result.markdown), [result.markdown]);
  const qg = result.quality_gate;
  const filename = result.output_file
    ? result.output_file.replace(/^.*[\\/]/, "")
    : "situation-analysis.md";
  const wordCount = result.markdown.split(/\s+/).filter(Boolean).length;

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(result.markdown);
    toast.success("Copied to clipboard");
  }, [result.markdown]);

  return (
    <Card>
      {/* Header row */}
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 space-y-0.5">
            <CardTitle className="flex items-center gap-2 text-base">
              <FileText className="h-4 w-4 shrink-0 text-primary" />
              <span className="truncate">{filename}</span>
            </CardTitle>
            <CardDescription>
              {wordCount.toLocaleString()} words
              {qg && (
                <>
                  {" · "}
                  <span className={qg.passed ? "text-green-500" : "text-red-400"}>
                    QG {qg.passed ? "pass" : "fail"} ·{" "}
                    {((qg.overall_score ?? 0) * 10).toFixed(1)}/10
                  </span>
                </>
              )}
            </CardDescription>
          </div>

          {/* Export toolbar */}
          <div className="flex shrink-0 items-center gap-1.5">
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs"
              onClick={() => downloadMarkdown(result.markdown, filename)}
            >
              <Download className="mr-1.5 h-3 w-3" />
              Markdown
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs"
              onClick={() => exportHtml(result.markdown, filename.replace(/\.md$/, ""))}
            >
              <Download className="mr-1.5 h-3 w-3" />
              HTML
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 p-0"
              onClick={handleCopy}
              title="Copy markdown"
            >
              <Copy className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Quality gate visualization */}
        {qg && qg.overall_score !== undefined && (
          <div className="rounded-lg border border-border bg-muted/10 p-4">
            <div className="mb-3 flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Quality Gate
              </span>
              <Badge variant={qg.passed ? "success" : "destructive"} className="text-[11px]">
                {qg.passed ? "PASS" : "FAIL"}
              </Badge>
            </div>
            <SAQualityGateChart qualityGate={qg} />
          </div>
        )}

        {/* Markdown preview + TOC tabs */}
        <Tabs defaultValue="preview">
          <TabsList>
            <TabsTrigger value="preview" className="flex items-center gap-1.5">
              <BookOpen className="h-3.5 w-3.5" />
              Preview
            </TabsTrigger>
            {toc.length > 0 && (
              <TabsTrigger value="toc">Sections ({toc.length})</TabsTrigger>
            )}
          </TabsList>

          <TabsContent value="preview" className="mt-3">
            <div className="max-h-[640px] overflow-y-auto rounded-md border border-border bg-background/60 px-5 py-4">
              <MarkdownRenderer content={result.markdown} />
            </div>
          </TabsContent>

          {toc.length > 0 && (
            <TabsContent value="toc" className="mt-3">
              <div className="rounded-md border border-border bg-background/60 px-4 py-3">
                <p className="mb-2 text-xs text-muted-foreground">
                  {toc.length} sections — click to jump (requires full-page render)
                </p>
                <TocSidebar entries={toc} />
              </div>
            </TabsContent>
          )}
        </Tabs>
      </CardContent>
    </Card>
  );
}

// ── Main SA Page ──────────────────────────────────────────

export function SAPage() {
  const { form, setField } = useFormStore();
  const writeSA = useWriteSA();
  const [formOpen, setFormOpen] = useState(true);

  const handleRun = useCallback(() => {
    writeSA.mutate(
      {
        countries: form.countries,
        disaster_types: form.disaster_types,
        title: form.sa_title || "Situation Analysis",
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
        onSuccess: () => { setFormOpen(false); },
      }
    );
  }, [form, writeSA]);

  const result = writeSA.data;

  return (
    <div className="space-y-6">
      {/* Page header */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2">
                <FlaskConical className="h-5 w-5 text-primary" />
                Situation Analysis
              </CardTitle>
              <CardDescription className="mt-1">
                Generate structured humanitarian situation reports with LLM-assisted drafting,
                configurable section templates, and quality gate scoring.
              </CardDescription>
            </div>
            {result && (
              <Badge
                variant={result.quality_gate?.passed ? "success" : "outline"}
                className="shrink-0"
              >
                {result.quality_gate?.passed ? (
                  <CheckCircle className="mr-1 h-3 w-3" />
                ) : (
                  <XCircle className="mr-1 h-3 w-3" />
                )}
                {result.quality_gate?.passed ? "Quality Pass" : "Last Run"}
              </Badge>
            )}
          </div>
        </CardHeader>
      </Card>

      {/* ── Configuration form (collapsible) ── */}
      <Card>
          <CardHeader className="pb-3">
            <button
              type="button"
              onClick={() => setFormOpen((o) => !o)}
              className="flex w-full items-center justify-between text-left"
            >
              <CardTitle className="text-base">Configuration</CardTitle>
              {formOpen ? (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              )}
            </button>
          </CardHeader>

          {formOpen && (
            <CardContent className="space-y-6">
              {/* Template selector */}
              <div className="space-y-2">
                <Label className="text-sm font-semibold">Template</Label>
                <TemplatePicker
                  value={form.sa_template}
                  onChange={(v) => setField("sa_template", v)}
                />
              </div>

              <Separator />

              {/* Scope: countries + hazard types */}
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Countries</Label>
                  <CountrySelect
                    value={form.countries}
                    onChange={(v) => setField("countries", v)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Disaster / Hazard Types</Label>
                  <HazardPicker
                    value={form.disaster_types}
                    onChange={(v) => setField("disaster_types", v)}
                  />
                </div>
              </div>

              {/* Event meta */}
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="sa-event-name">Event Name</Label>
                  <Input
                    id="sa-event-name"
                    placeholder="e.g. Cyclone Hidaya"
                    value={form.sa_event_name}
                    onChange={(e) => setField("sa_event_name", e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="sa-event-type">Event Type</Label>
                  <Input
                    id="sa-event-type"
                    placeholder="e.g. cyclone"
                    value={form.sa_event_type}
                    onChange={(e) => setField("sa_event_type", e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="sa-period">Period</Label>
                  <Input
                    id="sa-period"
                    placeholder="e.g. 2025-W22"
                    value={form.sa_period}
                    onChange={(e) => setField("sa_period", e.target.value)}
                  />
                </div>
              </div>

              <Separator />

              {/* Pipeline limits */}
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="sa-limit-events">Max Events</Label>
                  <Input
                    id="sa-limit-events"
                    type="number"
                    min={1}
                    max={500}
                    value={form.sa_limit_events}
                    onChange={(e) => setField("sa_limit_events", Number(e.target.value))}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="sa-limit-cycles">Max Cycles</Label>
                  <Input
                    id="sa-limit-cycles"
                    type="number"
                    min={1}
                    max={20}
                    value={form.limit_cycles}
                    onChange={(e) => setField("limit_cycles", Number(e.target.value))}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="sa-max-age">Max Age (days)</Label>
                  <Input
                    id="sa-max-age"
                    type="number"
                    min={1}
                    max={365}
                    value={form.max_age_days}
                    onChange={(e) => setField("max_age_days", Number(e.target.value))}
                  />
                </div>
              </div>

              <Separator />

              {/* Toggles */}
              <div className="flex flex-wrap gap-6">
                <div className="flex items-center gap-3">
                  <Switch
                    id="sa-use-llm"
                    checked={form.use_llm}
                    onCheckedChange={(v) => setField("use_llm", v)}
                  />
                  <Label htmlFor="sa-use-llm" className="cursor-pointer">
                    Use LLM drafting
                  </Label>
                </div>
                <div className="flex items-center gap-3">
                  <Switch
                    id="sa-quality-gate"
                    checked={form.sa_quality_gate}
                    onCheckedChange={(v) => setField("sa_quality_gate", v)}
                  />
                  <Label htmlFor="sa-quality-gate" className="cursor-pointer">
                    Quality gate scoring
                  </Label>
                </div>
              </div>

              {/* Run button */}
              <div className="flex items-center justify-end gap-3 pt-1">
                {writeSA.isError && (
                  <p className="text-sm text-destructive">{writeSA.error.message}</p>
                )}
                <Button onClick={handleRun} disabled={writeSA.isPending}>
                  {writeSA.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Generating…
                    </>
                  ) : (
                    <>
                      <Play className="mr-2 h-4 w-4" />
                      Generate Situation Analysis
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          )}
        </Card>

      {/* ── Loading state ── */}
      {writeSA.isPending && (
        <Card>
          <CardContent className="flex items-center gap-3 py-10">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <span className="text-sm text-muted-foreground">
              Running situation analysis — this may take several minutes…
            </span>
          </CardContent>
        </Card>
      )}

      {/* ── Output panel ── */}
      {result && !writeSA.isPending && <SAOutputPanel result={result} />}
    </div>
  );
}

