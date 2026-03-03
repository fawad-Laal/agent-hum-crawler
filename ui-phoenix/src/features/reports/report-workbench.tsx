/**
 * Project Phoenix — Phase 4 Report Workbench
 * Side-by-side AI vs Deterministic compare with section word-budget usage.
 * Integrates with existing workbench API endpoints and profile presets.
 */

import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Collapsible } from "@/components/ui/collapsible";
import { MarkdownRenderer } from "@/components/ui/markdown-renderer";
import { useFormStore } from "@/stores/form-store";
import {
  useRunWorkbench,
  useRerunLastWorkbench,
} from "@/hooks/use-mutations";
import { toast } from "sonner";
import {
  FlaskConical,
  Play,
  RotateCcw,
  Loader2,
  LayoutDashboard,
  BookOpen,
  Split,
  BarChart3,
} from "lucide-react";
import { useState, useCallback } from "react";
import type { WorkbenchResponse, SectionWordUsage } from "@/types";
import { PresetManagerModal } from "./preset-manager-modal";

// ── Section Word Usage Table ────────────────────────────────

function SectionWordUsageTable({
  usage,
  label,
}: {
  usage: SectionWordUsage;
  label: string;
}) {
  const entries = Object.entries(usage);
  if (entries.length === 0) return null;

  return (
    <div className="space-y-2">
      <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
        {label} — Word Budget
      </h4>
      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/30">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Section
              </th>
              <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Words
              </th>
              <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Limit
              </th>
              <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Usage
              </th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([section, { word_count, limit }]) => {
              const pct = limit > 0 ? (word_count / limit) * 100 : 0;
              const over = pct > 100;
              return (
                <tr key={section} className="border-b border-border/50 hover:bg-muted/10">
                  <td className="px-3 py-2 text-foreground/80">{section}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{word_count}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{limit}</td>
                  <td className="px-3 py-2 text-right">
                    <Badge variant={over ? "destructive" : pct > 80 ? "warning" : "success"}>
                      {pct.toFixed(0)}%
                    </Badge>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── View Mode Button ────────────────────────────────────────

function ViewModeButton({
  mode,
  activeMode,
  onSelect,
  icon: Icon,
  label,
}: {
  mode: string;
  activeMode: string;
  onSelect: (mode: string) => void;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}) {
  const isActive = mode === activeMode;
  return (
    <button
      onClick={() => onSelect(mode)}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer ${
        isActive
          ? "bg-background text-foreground shadow-sm"
          : "text-muted-foreground hover:text-foreground"
      }`}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
    </button>
  );
}

// ── Workbench Result Display ────────────────────────────────

function WorkbenchResult({ data }: { data: WorkbenchResponse }) {
  const [viewMode, setViewMode] = useState<"split" | "deterministic" | "ai">("split");

  return (
    <div className="space-y-4 mt-4">
      {/* View mode selector */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground font-medium uppercase tracking-wider">
          View
        </span>
        <div className="flex gap-1 rounded-lg bg-muted/30 p-1">
          <ViewModeButton mode="split" activeMode={viewMode} onSelect={(m) => setViewMode(m as "split")} icon={Split} label="Split" />
          <ViewModeButton mode="deterministic" activeMode={viewMode} onSelect={(m) => setViewMode(m as "deterministic")} icon={LayoutDashboard} label="Deterministic" />
          <ViewModeButton mode="ai" activeMode={viewMode} onSelect={(m) => setViewMode(m as "ai")} icon={BookOpen} label="AI" />
        </div>
      </div>

      {/* Split view */}
      {viewMode === "split" && (
        <div className="grid grid-cols-2 gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm flex items-center gap-2">
                <LayoutDashboard className="h-4 w-4 text-secondary" />
                Deterministic
              </CardTitle>
            </CardHeader>
            <CardContent>
              <MarkdownRenderer content={data.deterministic.markdown} compact />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-primary" />
                AI Assisted
              </CardTitle>
            </CardHeader>
            <CardContent>
              <MarkdownRenderer content={data.ai.markdown} compact />
            </CardContent>
          </Card>
        </div>
      )}

      {/* Single view */}
      {viewMode === "deterministic" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <LayoutDashboard className="h-4 w-4 text-secondary" />
              Deterministic Report
            </CardTitle>
          </CardHeader>
          <CardContent>
            <MarkdownRenderer content={data.deterministic.markdown} />
          </CardContent>
        </Card>
      )}

      {viewMode === "ai" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-primary" />
              AI Assisted Report
            </CardTitle>
          </CardHeader>
          <CardContent>
            <MarkdownRenderer content={data.ai.markdown} />
          </CardContent>
        </Card>
      )}

      {/* Section word usage comparison */}
      <Collapsible
        trigger={
          <span className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-primary" />
            Section Word Budget Analysis
          </span>
        }
      >
        <div className="grid md:grid-cols-2 gap-4">
          <SectionWordUsageTable
            usage={data.deterministic.section_word_usage}
            label="Deterministic"
          />
          <SectionWordUsageTable
            usage={data.ai.section_word_usage}
            label="AI"
          />
        </div>
      </Collapsible>
    </div>
  );
}

// ── Main Workbench Component ────────────────────────────────

export function ReportWorkbench() {
  const form = useFormStore((s) => s.form);
  const setField = useFormStore((s) => s.setField);
  const runWorkbench = useRunWorkbench();
  const rerunLast = useRerunLastWorkbench();
  const [result, setResult] = useState<WorkbenchResponse | null>(null);
  const [presetModalOpen, setPresetModalOpen] = useState(false);

  const isRunning = runWorkbench.isPending || rerunLast.isPending;

  const buildProfile = useCallback((): Record<string, unknown> => ({
    countries: form.countries,
    disaster_types: form.disaster_types,
    max_age_days: form.max_age_days,
    limit_cycles: form.limit_cycles,
    limit_events: form.limit_events,
    report_template: form.report_template,
    country_min_events: form.country_min_events,
    max_per_connector: form.max_per_connector,
    max_per_source: form.max_per_source,
  }), [form]);

  const handleRun = useCallback(() => {
    const profile = buildProfile();
    runWorkbench.mutate(profile, {
      onSuccess: (data) => {
        setResult(data);
        toast.success("Workbench compare complete");
      },
      onError: (err) => {
        toast.error(`Workbench failed: ${err.message}`);
      },
    });
  }, [buildProfile, runWorkbench]);

  const handleRerunLast = useCallback(() => {
    rerunLast.mutate(undefined, {
      onSuccess: (data) => {
        setResult(data);
        toast.success("Rerun complete");
      },
      onError: (err) => {
        toast.error(`Rerun failed: ${err.message}`);
      },
    });
  }, [rerunLast]);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FlaskConical className="h-5 w-5 text-primary" />
            Report Quality Workbench
          </CardTitle>
          <CardDescription>
            Side-by-side comparison of deterministic vs AI-generated reports.
            Configure parameters, run a compare, and analyze word-budget compliance.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Workbench parameters (inline) */}
          <Collapsible
            trigger={
              <span className="flex items-center gap-2">
                <FlaskConical className="h-4 w-4 text-primary" />
                Workbench Parameters
              </span>
            }
            defaultOpen
          >
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="wb-countries">Countries</Label>
                <Input
                  id="wb-countries"
                  value={form.countries}
                  onChange={(e) => setField("countries", e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="wb-disaster-types">Disaster Types</Label>
                <Input
                  id="wb-disaster-types"
                  value={form.disaster_types}
                  onChange={(e) => setField("disaster_types", e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="wb-template">Report Template</Label>
                <Input
                  id="wb-template"
                  value={form.report_template}
                  onChange={(e) => setField("report_template", e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="wb-max-age">Max Age (days)</Label>
                <Input
                  id="wb-max-age"
                  type="number"
                  value={form.max_age_days}
                  onChange={(e) => setField("max_age_days", Number(e.target.value))}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="wb-limit-cycles">Limit Cycles</Label>
                <Input
                  id="wb-limit-cycles"
                  type="number"
                  value={form.limit_cycles}
                  onChange={(e) => setField("limit_cycles", Number(e.target.value))}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="wb-limit-events">Limit Events</Label>
                <Input
                  id="wb-limit-events"
                  type="number"
                  value={form.limit_events}
                  onChange={(e) => setField("limit_events", Number(e.target.value))}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="wb-country-min">Country Min Events</Label>
                <Input
                  id="wb-country-min"
                  type="number"
                  value={form.country_min_events}
                  onChange={(e) => setField("country_min_events", Number(e.target.value))}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="wb-max-connector">Max / Connector</Label>
                <Input
                  id="wb-max-connector"
                  type="number"
                  value={form.max_per_connector}
                  onChange={(e) => setField("max_per_connector", Number(e.target.value))}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="wb-max-source">Max / Source</Label>
                <Input
                  id="wb-max-source"
                  type="number"
                  value={form.max_per_source}
                  onChange={(e) => setField("max_per_source", Number(e.target.value))}
                />
              </div>
            </div>
          </Collapsible>

          <Separator className="my-4" />

          {/* Action buttons */}
          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={handleRun} disabled={isRunning}>
              {isRunning ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Play className="h-4 w-4 mr-2" />
              )}
              Run Compare
            </Button>
            <Button variant="outline" onClick={handleRerunLast} disabled={isRunning}>
              <RotateCcw className="h-4 w-4 mr-2" />
              Rerun Last Profile
            </Button>
            <Button variant="secondary" onClick={() => setPresetModalOpen(true)}>
              <LayoutDashboard className="h-4 w-4 mr-2" />
              Manage Presets
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {result && <WorkbenchResult data={result} />}

      {/* Preset Manager Modal */}
      <PresetManagerModal
        open={presetModalOpen}
        onOpenChange={setPresetModalOpen}
        currentProfile={buildProfile()}
      />
    </div>
  );
}
