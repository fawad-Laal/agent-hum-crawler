import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Radio } from "lucide-react";

export function OperationsPage() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Radio className="h-5 w-5 text-primary" />
            Command Center
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            Operations module — will be built in Phase 3. This will include
            country selection, hazard type picker, cycle runner, report writer,
            and source check controls.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
