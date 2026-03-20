import { createContext } from "react";

export interface DepartmentCtx {
  department: string | null;
  setDepartment: (d: string | null) => void;
}

export const DepartmentCtx = createContext<DepartmentCtx>({ department: null, setDepartment: () => {} });
