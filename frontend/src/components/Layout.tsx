import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import TenantFilter from "./TenantFilter";
import { useDemo } from "../hooks/useDemo";
import { useTheme } from "../hooks/useTheme";
import { AskDrawer, BriefingDrawer } from "./AIDrawer";

const NAV_MAIN = [
  { to: "/", label: "Overview", icon: "M3.75 6A2.25 2.25 0 0 1 6 3.75h2.25A2.25 2.25 0 0 1 10.5 6v2.25a2.25 2.25 0 0 1-2.25 2.25H6a2.25 2.25 0 0 1-2.25-2.25V6ZM3.75 15.75A2.25 2.25 0 0 1 6 13.5h2.25a2.25 2.25 0 0 1 2.25 2.25V18a2.25 2.25 0 0 1-2.25 2.25H6A2.25 2.25 0 0 1 3.75 18v-2.25ZM13.5 6a2.25 2.25 0 0 1 2.25-2.25H18A2.25 2.25 0 0 1 20.25 6v2.25A2.25 2.25 0 0 1 18 10.5h-2.25a2.25 2.25 0 0 1-2.25-2.25V6ZM13.5 15.75a2.25 2.25 0 0 1 2.25-2.25H18a2.25 2.25 0 0 1 2.25 2.25V18A2.25 2.25 0 0 1 18 20.25h-2.25A2.25 2.25 0 0 1 13.5 18v-2.25Z" },
];

const NAV_WORKLOADS = [
  { to: "/ediscovery", label: "eDiscovery", icon: "m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" },
  { to: "/labels", label: "Labels", icon: "M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0 1 11.186 0Z" },
  { to: "/audit", label: "Audit", icon: "M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 0 0 2.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 0 0-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0A2.251 2.251 0 0 1 13.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25ZM6.75 12h.008v.008H6.75V12Zm0 3h.008v.008H6.75V15Zm0 3h.008v.008H6.75V18Z" },
  { to: "/dlp", label: "DLP", icon: "M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" },
  { to: "/irm", label: "IRM", icon: "M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" },
  { to: "/subject-rights", label: "Subject Rights", icon: "M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" },
  { to: "/comm-compliance", label: "Comm Compliance", icon: "M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 0 1-.825-.242m9.345-8.334a2.126 2.126 0 0 0-.476-.095 48.64 48.64 0 0 0-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0 0 11.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155" },
  { to: "/dlp-policies", label: "DLP Policies", icon: "M9 12.75 11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 0 1-1.043 3.296 3.745 3.745 0 0 1-3.296 1.043A3.745 3.745 0 0 1 12 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 0 1-3.296-1.043 3.745 3.745 0 0 1-1.043-3.296A3.745 3.745 0 0 1 3 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 0 1 1.043-3.296 3.746 3.746 0 0 1 3.296-1.043A3.746 3.746 0 0 1 12 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 0 1 3.296 1.043 3.746 3.746 0 0 1 1.043 3.296A3.745 3.745 0 0 1 21 12Z" },
  { to: "/irm-policies", label: "IRM Policies", icon: "M3.75 3v11.25A2.25 2.25 0 0 0 6 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0 1 18 16.5h-2.25m-7.5 0h7.5m-7.5 0-1 3m8.5-3 1 3m0 0 .5 1.5m-.5-1.5h-9.5m0 0-.5 1.5M9 11.25v1.5M12 9v3.75m3-6v6" },
  { to: "/sensitive-info", label: "Sensitive Info Types", icon: "M7.864 4.243A7.5 7.5 0 0 1 19.5 10.5c0 2.92-.556 5.709-1.568 8.268M5.742 6.364A7.465 7.465 0 0 0 4.5 10.5a48.667 48.667 0 0 0-1.488 8.768m5.827 0a48.34 48.34 0 0 1-2.063-8.185A6 6 0 0 1 12 4.5c3.314 0 6 2.686 6 6a48.734 48.734 0 0 1-1.462 8.268M14.745 3.09A9 9 0 0 0 12 3c-4.97 0-9 4.03-9 9a49.184 49.184 0 0 0-1.178 8.768" },
  { to: "/assessments", label: "Assessments", icon: "M11.35 3.836c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0A2.251 2.251 0 0 1 13.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m8.9-4.414c.376.023.75.05 1.124.08 1.131.094 1.976 1.057 1.976 2.192V16.5A2.25 2.25 0 0 1 18 18.75h-2.25m-7.5-10.5H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V18.75m-7.5-10.5h6.375c.621 0 1.125.504 1.125 1.125v9.375m-8.25-3 1.5 1.5 3-3.75" },
];

const NAV_ANALYTICS = [
  { to: "/trend", label: "Trend", icon: "M2.25 18 9 11.25l4.306 4.306a11.95 11.95 0 0 1 5.814-5.518l2.74-1.22m0 0-5.94-2.281m5.94 2.28-2.28 5.941" },
];

function NavIcon({ d }: { d: string }) {
  return (
    <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d={d} />
    </svg>
  );
}

type NavItem = { to: string; label: string; icon: string };

function NavSection({ label, items }: { label: string; items: NavItem[] }) {
  return (
    <div>
      <p className="px-4 pt-5 pb-1.5 text-[10px] font-semibold uppercase tracking-widest text-navy-400">{label}</p>
      {items.map((n) => (
        <NavLink
          key={n.to}
          to={n.to}
          end={n.to === "/"}
          className={({ isActive }) =>
            `flex items-center gap-2.5 px-4 py-2 text-sm transition-colors ${
              isActive
                ? "border-l-2 border-gold-500 bg-navy-800 font-medium text-gold-400"
                : "border-l-2 border-transparent text-navy-200 hover:bg-navy-800 hover:text-white"
            }`
          }
        >
          <NavIcon d={n.icon} />
          {n.label}
        </NavLink>
      ))}
    </div>
  );
}

export default function Layout() {
  const { demo, setDemo } = useDemo();
  const { dark, toggleDark } = useTheme();
  const [drawer, setDrawer] = useState<"briefing" | "ask" | null>(null);

  return (
    <div className="flex h-screen flex-col bg-slate-100 dark:bg-slate-950">
      {demo && (
        <div className="bg-navy-800 text-gold-400 text-xs font-semibold text-center py-1 tracking-wide">DEMO MODE</div>
      )}
      <div className="flex flex-1 overflow-hidden">
      <aside className="flex w-56 shrink-0 flex-col bg-navy-900">
        <div className="flex items-center gap-3 px-4 py-5">
          <svg className="h-8 w-8 shrink-0" viewBox="0 0 24 24" fill="none">
            <path d="M12 2 4 5.5v5c0 5.25 3.4 10.2 8 11.5 4.6-1.3 8-6.25 8-11.5v-5L12 2Z" fill="#b8860b" />
            <path d="m10 14.2-2.5-2.5-1.2 1.3 3.7 3.7 7-7-1.2-1.3-5.8 5.8Z" fill="#1a365d" />
          </svg>
          <div>
            <h1 className="text-sm font-bold text-white tracking-wide">Compliance</h1>
            <h1 className="text-sm font-bold text-gold-400 tracking-wide">Advisor</h1>
          </div>
        </div>
        <div className="border-t border-navy-700" />
        <nav className="flex-1 overflow-y-auto py-2">
          {NAV_MAIN.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-4 py-2 text-sm transition-colors ${
                  isActive
                    ? "border-l-2 border-gold-500 bg-navy-800 font-medium text-gold-400"
                    : "border-l-2 border-transparent text-navy-200 hover:bg-navy-800 hover:text-white"
                }`
              }
            >
              <NavIcon d={n.icon} />
              {n.label}
            </NavLink>
          ))}
          <NavSection label="Workloads" items={NAV_WORKLOADS} />
          <NavSection label="Analytics" items={NAV_ANALYTICS} />
        </nav>
      </aside>
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex items-center justify-between bg-navy-900 border-b border-navy-700 px-6 py-3">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setDrawer("briefing")}
              className="rounded-md border border-gold-500/60 px-3 py-1.5 text-sm font-medium text-gold-400 hover:bg-gold-500 hover:text-white transition-colors"
            >
              Executive Briefing
            </button>
            <button
              onClick={() => setDrawer("ask")}
              className="rounded-md border border-gold-500/60 px-3 py-1.5 text-sm font-medium text-gold-400 hover:bg-gold-500 hover:text-white transition-colors"
            >
              Ask AI
            </button>
            <button
              onClick={toggleDark}
              className="rounded-md px-2 py-1.5 text-navy-300 hover:text-white transition-colors"
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
            <label className="flex items-center gap-1.5 text-sm text-navy-300 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={demo}
                onChange={(e) => setDemo(e.target.checked)}
                className="h-3.5 w-3.5 rounded border-navy-500 text-gold-500 focus:ring-gold-500"
              />
              Demo
            </label>
            <TenantFilter />
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
