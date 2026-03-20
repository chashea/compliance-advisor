import { useContext } from "react";
import { DepartmentCtx } from "../contexts/DepartmentCtx";

export function useDepartment() {
  return useContext(DepartmentCtx);
}
