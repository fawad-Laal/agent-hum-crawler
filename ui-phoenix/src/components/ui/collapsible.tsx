import { cn } from "@/lib/utils";
import { useState, type HTMLAttributes, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";

interface CollapsibleProps extends HTMLAttributes<HTMLDivElement> {
  defaultOpen?: boolean;
  trigger: ReactNode;
}

export function Collapsible({
  className,
  defaultOpen = false,
  trigger,
  children,
  ...props
}: CollapsibleProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={cn("space-y-2", className)} {...props}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm font-medium text-foreground/90 hover:bg-accent/50 transition-colors cursor-pointer"
      >
        {trigger}
        <ChevronDown
          className={cn(
            "h-4 w-4 text-muted-foreground transition-transform duration-200",
            open && "rotate-180"
          )}
        />
      </button>
      {open && <div className="px-3">{children}</div>}
    </div>
  );
}
