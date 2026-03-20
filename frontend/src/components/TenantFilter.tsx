import { useEffect, useState } from "react";
import { post } from "../api/client";
import type { OverviewResponse, Tenant } from "../types";
import { useTenant } from "../hooks/useTenant";

export default function TenantFilter() {
  const { tenantId, setTenantId } = useTenant();
  const [tenants, setTenants] = useState<Tenant[]>([]);

  useEffect(() => {
    post<OverviewResponse>("overview").then((d) => {
      setTenants(d.tenants ?? []);
    });
  }, []);

  return (
    <select
      value={tenantId ?? ""}
      onChange={(e) => setTenantId(e.target.value || null)}
      className="rounded border border-navy-600 bg-navy-800 px-3 py-1.5 text-sm text-navy-100 focus:border-gold-500 focus:outline-none"
    >
      <option value="">All Tenants</option>
      {tenants.map((t) => (
        <option key={t.tenant_id} value={t.tenant_id}>
          {t.display_name}
        </option>
      ))}
    </select>
  );
}
