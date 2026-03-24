import { msalInstance } from "../auth/msalInstance";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const API_SCOPE = import.meta.env.VITE_ENTRA_CLIENT_ID
  ? `api://${import.meta.env.VITE_ENTRA_CLIENT_ID}/access_as_user`
  : "";

async function getAuthHeaders(): Promise<Record<string, string>> {
  if (!msalInstance || !API_SCOPE) return {};
  const accounts = msalInstance.getAllAccounts();
  if (accounts.length === 0) return {};
  try {
    const result = await msalInstance.acquireTokenSilent({
      scopes: [API_SCOPE],
      account: accounts[0],
    });
    return { Authorization: `Bearer ${result.accessToken}` };
  } catch {
    return {};
  }
}

export async function post<T>(endpoint: string, body?: Record<string, unknown>, demo?: boolean): Promise<T> {
  if (demo) {
    const { getDemoData } = await import("../demo/data");
    return getDemoData(endpoint, body) as T;
  }
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${BASE_URL}/api/advisor/${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders },
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error ?? `Request failed: ${res.status}`);
  }
  return res.json();
}
