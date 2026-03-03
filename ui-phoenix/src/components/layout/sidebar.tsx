import { NavLink } from "react-router-dom";
import { useUIStore } from "@/stores/ui-store";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Radio,
  FileText,
  Activity,
  Satellite,
  FlaskConical,
  Settings,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

const navItems = [
  { label: "Overview", path: "/", icon: LayoutDashboard },
  { label: "Operations", path: "/operations", icon: Radio },
  { label: "Reports", path: "/reports", icon: FileText },
  { label: "Sources", path: "/sources", icon: Satellite },
  { label: "System", path: "/system", icon: Activity },
  { label: "Situation Analysis", path: "/sa", icon: FlaskConical },
  { label: "Settings", path: "/settings", icon: Settings },
];

export function Sidebar() {
  const { sidebarOpen, toggleSidebar } = useUIStore();

  return (
    <aside
      aria-label="Main navigation"
      className={cn(
        "fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-border bg-card transition-all duration-300",
        sidebarOpen ? "w-60" : "w-16"
      )}
    >
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 border-b border-border px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/20">
          <Radio className="h-4 w-4 text-primary" />
        </div>
        {sidebarOpen && (
          <span className="text-sm font-semibold tracking-tight whitespace-nowrap">
            Agent HUM
          </span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-2 py-4">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              )
            }
          >
            <item.icon className="h-4 w-4 shrink-0" />
            {sidebarOpen && <span className="truncate">{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Collapse toggle */}
      <div className="border-t border-border p-2">
        <button
          onClick={toggleSidebar}
          className="flex w-full items-center justify-center rounded-lg p-2.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground cursor-pointer"
          aria-label={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
        >
          {sidebarOpen ? (
            <ChevronLeft className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>
      </div>
    </aside>
  );
}
