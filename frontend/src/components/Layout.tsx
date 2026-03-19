import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import DepartmentFilter from "./DepartmentFilter";
import { useDemo } from "./DemoContext";
import { useTheme } from "./ThemeContext";
import { AskDrawer, BriefingDrawer } from "./AIDrawer";

const NAV = [
  { to: "/", label: "Overview" },
  { to: "/ediscovery", label: "eDiscovery" },
  { to: "/labels", label: "Labels" },
  { to: "/audit", label: "Audit" },
  { to: "/dlp", label: "DLP" },
  { to: "/irm", label: "IRM" },
  { to: "/subject-rights", label: "Subject Rights" },
  { to: "/comm-compliance", label: "Comm Compliance" },
  { to: "/trend", label: "Trend" },
];

export default function Layout() {
  const { demo, setDemo } = useDemo();
  const { dark, toggleDark } = useTheme();
  const [drawer, setDrawer] = useState<"briefing" | "ask" | null>(null);

  return (
    <div className="flex h-screen flex-col bg-slate-50 dark:bg-slate-950">
      {demo && (
        <div className="bg-amber-500 text-white text-xs font-semibold text-center py-1">DEMO MODE</div>
      )}
      <div className="flex flex-1 overflow-hidden">
      <aside className="flex w-56 shrink-0 flex-col border-r border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
        <div className="border-b border-slate-200 dark:border-slate-700 px-4 py-4">
          <h1 className="text-lg font-semibold text-slate-800 dark:text-slate-100">Compliance Advisor</h1>
        </div>
        <nav className="flex-1 overflow-y-auto py-2">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) =>
                `block px-4 py-2 text-sm ${isActive ? "bg-blue-50 dark:bg-blue-900/30 font-medium text-blue-700 dark:text-blue-400" : "text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"}`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex items-center justify-between border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-6 py-3">
          <span className="text-sm text-slate-500 dark:text-slate-400">Microsoft 365 Compliance Dashboard</span>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setDrawer("briefing")}
              className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
            >
              Executive Briefing
            </button>
            <button
              onClick={() => setDrawer("ask")}
              className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
            >
              Ask AI
            </button>
            <button
              onClick={toggleDark}
              className="rounded-md px-2 py-1.5 text-sm text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
              title={dark ? "Switch to light mode" : "Switch to dark mode"}
            >
              {dark ? (
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
                </svg>
              ) : (
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
                </svg>
              )}
            </button>
            <label className="flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={demo}
                onChange={(e) => setDemo(e.target.checked)}
                className="h-3.5 w-3.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
              />
              Demo Data
            </label>
            <DepartmentFilter />
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
      </div>

      {drawer === "briefing" && <BriefingDrawer onClose={() => setDrawer(null)} />}
      {drawer === "ask" && <AskDrawer onClose={() => setDrawer(null)} />}
    </div>
  );
}
