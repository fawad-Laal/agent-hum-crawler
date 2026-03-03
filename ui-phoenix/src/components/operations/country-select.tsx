/**
 * CountrySelect — Multi-select chip component for countries
 * Parses comma-separated string from formStore, renders as removable chips,
 * and allows adding new countries via text input.
 */

import { useState, useCallback, type KeyboardEvent } from "react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { X, Plus } from "lucide-react";

interface CountrySelectProps {
  /** Comma-separated country string (e.g. "Ethiopia,Madagascar") */
  value: string;
  /** Called with updated comma-separated string */
  onChange: (value: string) => void;
  /** Optional placeholder text */
  placeholder?: string;
}

/** Parse comma-sep string to trimmed array, filtering blanks */
function parseChips(raw: string): string[] {
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function CountrySelect({
  value,
  onChange,
  placeholder = "Add country…",
}: CountrySelectProps) {
  const [input, setInput] = useState("");
  const chips = parseChips(value);

  const addCountry = useCallback(
    (name: string) => {
      const trimmed = name.trim();
      if (!trimmed) return;
      // Prevent duplicates (case-insensitive)
      if (chips.some((c) => c.toLowerCase() === trimmed.toLowerCase())) return;
      onChange([...chips, trimmed].join(","));
      setInput("");
    },
    [chips, onChange]
  );

  const removeCountry = useCallback(
    (idx: number) => {
      const next = chips.filter((_, i) => i !== idx);
      onChange(next.join(","));
    },
    [chips, onChange]
  );

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addCountry(input);
    }
    // Backspace on empty input removes last chip
    if (e.key === "Backspace" && !input && chips.length > 0) {
      removeCountry(chips.length - 1);
    }
  };

  return (
    <div className="space-y-2">
      {/* Chip display */}
      {chips.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {chips.map((country, idx) => (
            <Badge
              key={`${country}-${idx}`}
              variant="secondary"
              className="gap-1 pr-1 cursor-pointer hover:bg-secondary/40"
            >
              {country}
              <button
                type="button"
                onClick={() => removeCountry(idx)}
                className="rounded-full p-0.5 hover:bg-destructive/20 transition-colors"
                aria-label={`Remove ${country}`}
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="flex gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="flex-1"
        />
        <button
          type="button"
          onClick={() => addCountry(input)}
          disabled={!input.trim()}
          className="inline-flex items-center justify-center h-10 w-10 rounded-lg border border-border bg-background/50 hover:bg-accent transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          aria-label="Add country"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
