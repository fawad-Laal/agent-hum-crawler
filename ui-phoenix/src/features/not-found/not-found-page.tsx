import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { Ghost } from "lucide-react";

export function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col items-center justify-center gap-4 py-20">
      <Ghost className="h-12 w-12 text-muted-foreground" />
      <h1 className="text-2xl font-semibold">404 — Page Not Found</h1>
      <p className="text-sm text-muted-foreground">
        The page you're looking for doesn't exist.
      </p>
      <Button variant="outline" onClick={() => void navigate("/")}>
        Back to Overview
      </Button>
    </div>
  );
}
