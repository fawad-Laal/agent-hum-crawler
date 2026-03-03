import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { FlaskConical } from "lucide-react";

export function SAPage() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FlaskConical className="h-5 w-5 text-primary" />
            Situation Analysis
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            Situation Analysis module — will be built in Phase 6. This will
            include SA form, quality gate visualization (6-dimension bar chart),
            markdown preview, template selector, and export options.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
