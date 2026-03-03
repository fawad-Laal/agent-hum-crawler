/**
 * Project Phoenix — Markdown Renderer
 * Renders markdown reports with GFM tables, styled for the dark intelligence theme.
 * Uses react-markdown with remark-gfm for full table/strikethrough/autolink support.
 */

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

interface MarkdownRendererProps extends HTMLAttributes<HTMLDivElement> {
  content: string;
  /** Compact mode reduces spacing for side-by-side views */
  compact?: boolean;
}

export function MarkdownRenderer({ content, compact = false, className, ...props }: MarkdownRendererProps) {
  return (
    <div
      className={cn(
        "prose prose-invert max-w-none",
        compact ? "prose-sm" : "prose-base",
        // Headings
        "[&_h1]:text-foreground [&_h1]:text-xl [&_h1]:font-bold [&_h1]:border-b [&_h1]:border-border [&_h1]:pb-2 [&_h1]:mb-4",
        "[&_h2]:text-foreground [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:mt-6 [&_h2]:mb-3",
        "[&_h3]:text-foreground/90 [&_h3]:text-base [&_h3]:font-medium [&_h3]:mt-4 [&_h3]:mb-2",
        // Tables
        "[&_table]:w-full [&_table]:text-sm [&_table]:border-collapse",
        "[&_thead]:bg-muted/30",
        "[&_th]:text-left [&_th]:px-3 [&_th]:py-2 [&_th]:text-xs [&_th]:font-medium [&_th]:uppercase [&_th]:tracking-wider [&_th]:text-muted-foreground [&_th]:border-b [&_th]:border-border",
        "[&_td]:px-3 [&_td]:py-2 [&_td]:text-sm [&_td]:text-foreground/80 [&_td]:border-b [&_td]:border-border/50",
        "[&_tr:hover]:bg-muted/10",
        // Lists
        "[&_ul]:list-disc [&_ul]:pl-6 [&_ul]:space-y-1",
        "[&_ol]:list-decimal [&_ol]:pl-6 [&_ol]:space-y-1",
        "[&_li]:text-foreground/80 [&_li]:text-sm",
        // Paragraphs
        "[&_p]:text-foreground/80 [&_p]:leading-relaxed [&_p]:mb-3",
        // Strong / emphasis
        "[&_strong]:text-foreground [&_strong]:font-semibold",
        "[&_em]:text-foreground/70 [&_em]:italic",
        // Links
        "[&_a]:text-secondary [&_a]:underline [&_a]:underline-offset-2 hover:[&_a]:text-secondary/80",
        // Code
        "[&_code]:text-xs [&_code]:bg-muted/40 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded [&_code]:font-mono [&_code]:text-primary/90",
        "[&_pre]:bg-muted/20 [&_pre]:border [&_pre]:border-border [&_pre]:rounded-lg [&_pre]:p-4 [&_pre]:overflow-x-auto",
        "[&_pre_code]:bg-transparent [&_pre_code]:p-0",
        // Blockquotes
        "[&_blockquote]:border-l-2 [&_blockquote]:border-primary/50 [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-muted-foreground",
        // HR
        "[&_hr]:border-border [&_hr]:my-6",
        className,
      )}
      {...props}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
