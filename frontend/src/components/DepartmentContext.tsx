import { useState, type ReactNode } from "react";
import { DepartmentCtx } from "../contexts/DepartmentCtx";

export function DepartmentProvider({ children }: { children: ReactNode }) {
  const [department, setDepartment] = useState<string | null>(null);
  return <DepartmentCtx.Provider value={{ department, setDepartment }}>{children}</DepartmentCtx.Provider>;
}
