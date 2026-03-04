import { useHealth } from "@/hooks/use-queries";
import { Badge } from "@/components/ui/badge";
import { GlobalJobBadge } from "@/components/ui/global-job-badge";
import { RefreshCw } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";

interface HeaderProps {
  title: string;
}

export function Header({ title }: HeaderProps) {
  const { data: health, isLoading } = useHealth();
  const queryClient = useQueryClient();

  const handleRefresh = () => {
    void queryClient.invalidateQueries();
  };

  const healthVariant = isLoading
    ? "secondary" as const
    : health?.status === "ok"
      ? "success" as const
      : "destructive" as const;

  const healthLabel = isLoading
    ? "Checking…"
    : health?.status === "ok"
      ? "Backend Online"
      : "Backend Offline";

  return (
    <header className="flex h-16 items-center justify-between border-b border-border bg-card/50 px-6 backdrop-blur-sm">
      <h1 className="text-lg font-semibold tracking-tight">{title}</h1>

      <div className="flex items-center gap-3">
        {/* Active background jobs */}
        <GlobalJobBadge />

        {/* Backend status */}
        <Badge variant={healthVariant}>
          {healthLabel}
        </Badge>

        {/* Refresh all queries */}
        <Button variant="ghost" size="icon" onClick={handleRefresh} aria-label="Refresh data">
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
