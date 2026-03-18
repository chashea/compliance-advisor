import { NavLink, Outlet } from "react-router-dom";
import DepartmentFilter from "./DepartmentFilter";

const NAV = [
  { to: "/", label: "Overview" },
  { to: "/ediscovery", label: "eDiscovery" },
  { to: "/labels", label: "Labels" },
  { to: "/audit", label: "Audit" },
  { to: "/dlp", label: "DLP" },
  { to: "/irm", label: "IRM" },
  { to: "/subject-rights", label: "Subject Rights" },
  { to: "/comm-compliance", label: "Comm Compliance" },
  { to: "/info-barriers", label: "Info Barriers" },
  { to: "/governance", label: "Governance" },
  { to: "/trend", label: "Trend" },
  { to: "/advisor", label: "AI Advisor" },
];

export default function Layout() {
  return (
    <div className="flex h-screen flex-col bg-slate-50">
      {import.meta.env.VITE_DEMO === "true" && (
        <div className="bg-amber-500 text-white text-xs font-semibold text-center py-1">DEMO MODE</div>
      )}
      <div className="flex flex-1 overflow-hidden">
      <aside className="flex w-56 shrink-0 flex-col border-r border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-4 py-4">
          <h1 className="text-lg font-semibold text-slate-800">Compliance Advisor</h1>
        </div>
        <nav className="flex-1 overflow-y-auto py-2">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) =>
                `block px-4 py-2 text-sm ${isActive ? "bg-blue-50 font-medium text-blue-700" : "text-slate-600 hover:bg-slate-50"}`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
          <span className="text-sm text-slate-500">Microsoft 365 Compliance Dashboard</span>
          <DepartmentFilter />
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
      </div>
    </div>
  );
}
