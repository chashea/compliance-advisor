import { useContext } from "react";
import { TenantCtx } from "../contexts/TenantCtx";

export function useTenant() {
  return useContext(TenantCtx);
}
