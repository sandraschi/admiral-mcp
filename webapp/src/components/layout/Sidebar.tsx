import { useState } from "react";
import { NavLink } from "react-router-dom";
import { Anchor, ChevronLeft, ChevronRight, LayoutDashboard } from "lucide-react";
import clsx from "clsx";

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={clsx(
        "flex flex-col border-r border-zinc-800 bg-zinc-900/50 backdrop-blur transition-all duration-200",
        collapsed ? "w-16" : "w-56",
      )}
    >
      <div className="flex items-center gap-3 px-4 py-4 border-b border-zinc-800">
        <Anchor className="h-7 w-7 text-amber-500 shrink-0" />
        {!collapsed && (
          <span className="font-semibold text-sm text-zinc-100">Admiral</span>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="ml-auto rounded p-1 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>

      <nav className="flex-1 py-4 space-y-1 px-2">
        <NavLink
          to="/"
          className={({ isActive }) =>
            clsx(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
              isActive
                ? "bg-amber-500/10 text-amber-500"
                : "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/50",
            )
          }
        >
          <LayoutDashboard className="h-4 w-4 shrink-0" />
          {!collapsed && "Dashboard"}
        </NavLink>
      </nav>

      <div className="border-t border-zinc-800 px-4 py-3">
        {!collapsed && (
          <span className="text-xs text-zinc-600">v0.1.0</span>
        )}
      </div>
    </aside>
  );
}
