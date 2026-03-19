import { useEffect, useState } from "react";
import { post } from "../api/client";
import type { OverviewResponse } from "../types";
import { useDepartment } from "./DepartmentContext";

export default function DepartmentFilter() {
  const { department, setDepartment } = useDepartment();
  const [departments, setDepartments] = useState<string[]>([]);

  useEffect(() => {
    post<OverviewResponse>("overview").then((d) => {
      const depts = [...new Set(d.tenants.map((t) => t.department).filter(Boolean))].sort();
      setDepartments(depts);
    });
  }, []);

  return (
    <select
      value={department ?? ""}
      onChange={(e) => setDepartment(e.target.value || null)}
      className="rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-1.5 text-sm text-slate-700 dark:text-slate-200 focus:border-blue-500 focus:outline-none"
    >
      <option value="">All Departments</option>
      {departments.map((d) => (
        <option key={d} value={d}>
          {d}
        </option>
      ))}
    </select>
  );
}
