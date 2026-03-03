/**
 * Project Phoenix — Phase 4 Report Detail View
 * Full-screen markdown-rendered report with export options.
 * Navigated to via /reports/:name
 */

import { useParams, useNavigate } from "react-router-dom";
import { useReport } from "@/hooks/use-queries";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { MarkdownRenderer } from "@/components/ui/markdown-renderer";
import {
  ArrowLeft,
  FileText,
  Download,
  FileJson,
  FileType2,
  Copy,
  Check,
} from "lucide-react";
import { useState, useCallback, useMemo } from "react";
import { toast } from "sonner";

/** Parse report metadata from filename (e.g. report-20260302T091804Z.md) */
function parseReportMeta(name: string) {
  const match = name.match(/^(report|situation-analysis)-(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z\.md$/);
  if (!match) return { type: "report" as const, date: null };
  const [, type, y, mo, d, h, mi, s] = match;
  const date = new Date(`${y}-${mo}-${d}T${h}:${mi}:${s}Z`);
  return {
    type: type === "situation-analysis" ? "sa" as const : "report" as const,
    date: isNaN(date.getTime()) ? null : date,
  };
}

/** Download a blob with a given filename */
function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function ReportDetailPage() {
  const { name } = useParams<{ name: string }>();
  const navigate = useNavigate();
  const { data, isLoading, error } = useReport(name ?? null);
  const [copied, setCopied] = useState(false);
  const meta = useMemo(
    () => (name ? parseReportMeta(name) : { type: "report" as const, date: null }),
    [name],
  );

  const { wordCount, sectionCount, sectionTitles } = useMemo(() => {
    if (!data?.markdown) return { wordCount: 0, sectionCount: 0, sectionTitles: [] as string[] };
    const lines = data.markdown.split("\n");
    const titles = lines.filter((l) => l.startsWith("## ")).map((l) => l.replace(/^##\s+/, ""));
    return {
      wordCount: data.markdown.split(/\s+/).filter(Boolean).length,
      sectionCount: titles.length,
      sectionTitles: titles,
    };
  }, [data?.markdown]);

  const handleCopyMarkdown = useCallback(() => {
    if (!data?.markdown) return;
    void navigator.clipboard.writeText(data.markdown).then(
      () => {
        setCopied(true);
        toast.success("Markdown copied to clipboard");
        setTimeout(() => setCopied(false), 2000);
      },
      () => {
        toast.error("Failed to copy — clipboard access denied");
      },
    );
  }, [data?.markdown]);

  const handleExportMarkdown = useCallback(() => {
    if (!data?.markdown || !name) return;
    const blob = new Blob([data.markdown], { type: "text/markdown" });
    downloadBlob(blob, name);
    toast.success("Markdown file downloaded");
  }, [data?.markdown, name]);

  const handleExportJSON = useCallback(() => {
    if (!data || !name) return;
    const jsonContent = JSON.stringify(
      {
        name: data.name,
        generated: meta.date?.toISOString() ?? null,
        type: meta.type,
        markdown: data.markdown,
        wordCount,
        sections: sectionTitles,
      },
      null,
      2,
    );
    const blob = new Blob([jsonContent], { type: "application/json" });
    downloadBlob(blob, name.replace(/\.md$/, ".json"));
    toast.success("JSON export downloaded");
  }, [data, name, meta, wordCount, sectionTitles]);

  const handleExportHTML = useCallback(() => {
    if (!data?.markdown || !name) return;
    // Render a simple standalone HTML page with the markdown content
    const htmlContent = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${data.name}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 2rem; background: #f8f9fa; color: #1a1a2e; line-height: 1.6; }
    h1 { border-bottom: 2px solid #e2e8f0; padding-bottom: 0.5rem; }
    h2 { color: #2d3748; margin-top: 2rem; }
    table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
    th, td { border: 1px solid #e2e8f0; padding: 0.5rem 0.75rem; text-align: left; }
    th { background: #edf2f7; font-weight: 600; }
    ul, ol { padding-left: 1.5rem; }
    blockquote { border-left: 3px solid #3182ce; padding-left: 1rem; color: #4a5568; }
    code { background: #edf2f7; padding: 0.125rem 0.375rem; border-radius: 0.25rem; font-size: 0.875em; }
    pre { background: #2d3748; color: #e2e8f0; padding: 1rem; border-radius: 0.5rem; overflow-x: auto; }
    pre code { background: transparent; }
    .meta { color: #718096; font-size: 0.875rem; margin-bottom: 2rem; }
  </style>
</head>
<body>
  <div class="meta">Exported from Agent HUM Crawler Dashboard — ${new Date().toISOString()}</div>
  <div id="content">${data.markdown.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</div>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"><\/script>
  <script>document.getElementById('content').innerHTML = marked.parse(document.getElementById('content').textContent);<\/script>
</body>
</html>`;
    const blob = new Blob([htmlContent], { type: "text/html" });
    downloadBlob(blob, name.replace(/\.md$/, ".html"));
    toast.success("HTML export downloaded");
  }, [data, name]);

  return (
    <div className="space-y-4">
      {/* Navigation header */}
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => void navigate("/reports")}
          className="gap-1.5"
        >
          <ArrowLeft className="h-4 w-4" />
          Reports
        </Button>
        {name && (
          <span className="text-sm text-muted-foreground truncate max-w-md">
            {name}
          </span>
        )}
      </div>

      {/* Error state */}
      {error && (
        <Card>
          <CardContent>
            <p className="text-destructive text-sm py-4">
              Failed to load report: {error.message}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Loading state */}
      {isLoading && (
        <Card>
          <CardContent className="space-y-3 py-6">
            <Skeleton className="h-8 w-3/4" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-4 w-4/6" />
          </CardContent>
        </Card>
      )}

      {/* Report content */}
      {data && (
        <>
          {/* Report header */}
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3 min-w-0">
                  <FileText className="h-5 w-5 text-primary shrink-0" />
                  <CardTitle className="truncate">{data.name}</CardTitle>
                  <Badge
                    variant={meta.type === "sa" ? "secondary" : "default"}
                  >
                    {meta.type === "sa" ? "Situation Analysis" : "Report"}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <Badge variant="outline">{wordCount.toLocaleString()} words</Badge>
                  <Badge variant="outline">{sectionCount} sections</Badge>
                  {meta.date && (
                    <Badge variant="outline">
                      {meta.date.toLocaleDateString("en-GB", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </Badge>
                  )}
                </div>
              </div>
            </CardHeader>

            {/* Export toolbar */}
            <CardContent>
              <div className="flex flex-wrap items-center gap-2 pb-4 border-b border-border mb-4">
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider mr-2">
                  Export
                </span>
                <Button variant="outline" size="sm" onClick={handleExportMarkdown}>
                  <Download className="h-3.5 w-3.5 mr-1.5" />
                  Markdown
                </Button>
                <Button variant="outline" size="sm" onClick={handleExportHTML}>
                  <FileType2 className="h-3.5 w-3.5 mr-1.5" />
                  HTML
                </Button>
                <Button variant="outline" size="sm" onClick={handleExportJSON}>
                  <FileJson className="h-3.5 w-3.5 mr-1.5" />
                  JSON
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCopyMarkdown}
                  className="ml-auto"
                >
                  {copied ? (
                    <Check className="h-3.5 w-3.5 mr-1.5 text-status-pass" />
                  ) : (
                    <Copy className="h-3.5 w-3.5 mr-1.5" />
                  )}
                  {copied ? "Copied" : "Copy MD"}
                </Button>
              </div>

              {/* Rendered markdown */}
              <MarkdownRenderer content={data.markdown} />
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
