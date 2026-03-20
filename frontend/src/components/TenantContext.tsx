import { useState, type ReactNode } from "react";
import { TenantCtx } from "../contexts/TenantCtx";

export function TenantProvider({ children }: { children: ReactNode }) {
  const [tenantId, setTenantId] = useState<string | null>(null);
  return <TenantCtx.Provider value={{ tenantId, setTenantId }}>{children}</TenantCtx.Provider>;
}
