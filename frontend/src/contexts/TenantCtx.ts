import { createContext } from "react";

export interface TenantCtx {
  tenantId: string | null;
  setTenantId: (id: string | null) => void;
}

export const TenantCtx = createContext<TenantCtx>({ tenantId: null, setTenantId: () => {} });
