import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Satellite } from "lucide-react";

export function SourcesPage() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Satellite className="h-5 w-5 text-primary" />
            Source Intelligence
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            Source intelligence module — will be built in Phase 5. This will
            include source health table, connector diagnostics, freshness trend
            charts, and stale-source alerts.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
