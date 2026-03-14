const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const IS_DEMO = import.meta.env.VITE_DEMO === "true";

export async function post<T>(endpoint: string, body?: Record<string, unknown>): Promise<T> {
  if (IS_DEMO) {
    const { getDemoData } = await import("../demo/data");
    return getDemoData(endpoint, body) as T;
  }
  const res = await fetch(`${BASE_URL}/api/advisor/${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error ?? `Request failed: ${res.status}`);
  }
  return res.json();
}
