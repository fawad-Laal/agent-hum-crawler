/**
 * HazardPicker — Multi-select chip component for disaster/hazard types
 * Shows available types from system info API as toggleable chips.
 * Binds to formStore comma-separated disaster_types string.
 */

import { useCallback } from "react";
import { Badge } from "@/components/ui/badge";
import { useSystemInfo } from "@/hooks/use-queries";
import { Skeleton } from "@/components/ui/skeleton";
import {
  CloudRain,
  Flame,
  Wind,
  Droplets,
  Swords,
  Bug,
  Mountain,
  Waves,
  AlertTriangle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface HazardPickerProps {
  /** Comma-separated hazard types string */
  value: string;
  /** Called with updated comma-separated string */
  onChange: (value: string) => void;
}

/** Map hazard keywords to icons */
const HAZARD_ICONS: Record<string, LucideIcon> = {
  flood: Droplets,
  cyclone: Wind,
  storm: Wind,
  drought: CloudRain,
  wildfire: Flame,
  fire: Flame,
  conflict: Swords,
  epidemic: Bug,
  disease: Bug,
  earthquake: Mountain,
  tsunami: Waves,
  volcano: Mountain,
};

function getHazardIcon(hazard: string): LucideIcon {
  const lower = hazard.toLowerCase();
  for (const [key, icon] of Object.entries(HAZARD_ICONS)) {
    if (lower.includes(key)) return icon;
  }
  return AlertTriangle;
}

/** Parse comma-sep string to trimmed array */
function parseSelected(raw: string): string[] {
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function HazardPicker({ value, onChange }: HazardPickerProps) {
  const { data: systemInfo, isLoading } = useSystemInfo();

  const selected = parseSelected(value);

  const toggle = useCallback(
    (hazard: string) => {
      const isSelected = selected.some(
        (s) => s.toLowerCase() === hazard.toLowerCase()
      );
      const next = isSelected
        ? selected.filter((s) => s.toLowerCase() !== hazard.toLowerCase())
        : [...selected, hazard];
      onChange(next.join(","));
    },
    [selected, onChange]
  );

  if (isLoading) {
    return (
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-24 rounded-md" />
        ))}
      </div>
    );
  }

  const availableTypes = systemInfo?.allowed_disaster_types ?? [];

  if (availableTypes.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No hazard types available from system info.
      </p>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {availableTypes.map((hazard) => {
        const isActive = selected.some(
          (s) => s.toLowerCase() === hazard.toLowerCase()
        );
        const Icon = getHazardIcon(hazard);

        return (
          <button
            key={hazard}
            type="button"
            onClick={() => toggle(hazard)}
            className="cursor-pointer"
          >
            <Badge
              variant={isActive ? "default" : "outline"}
              className={`gap-1.5 px-3 py-1.5 text-sm transition-all ${
                isActive
                  ? "ring-1 ring-primary/50 shadow-sm shadow-primary/10"
                  : "opacity-60 hover:opacity-100"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {hazard}
            </Badge>
          </button>
        );
      })}
    </div>
  );
}
