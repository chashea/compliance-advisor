import { createContext, useContext, useState, type ReactNode } from "react";

interface DepartmentCtx {
  department: string | null;
  setDepartment: (d: string | null) => void;
}

const Ctx = createContext<DepartmentCtx>({ department: null, setDepartment: () => {} });

export function DepartmentProvider({ children }: { children: ReactNode }) {
  const [department, setDepartment] = useState<string | null>(null);
  return <Ctx.Provider value={{ department, setDepartment }}>{children}</Ctx.Provider>;
}

export function useDepartment() {
  return useContext(Ctx);
}
