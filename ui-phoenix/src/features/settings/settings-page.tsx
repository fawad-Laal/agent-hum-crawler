import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Settings } from "lucide-react";

export function SettingsPage() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5 text-primary" />
            Settings
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            Settings module — will be built in Phase 9. This will include user
            preferences, dark/light theme toggle, compact view, default filters,
            and multi-workspace configuration.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
