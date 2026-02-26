# Connecting to an M365 GCC tenant

**M365 GCC (Government Community Cloud) uses the same global endpoints as commercial Microsoft 365.** You do not need to change any Compliance Advisor settings to connect to an M365 GCC tenant.

**Data flow:** The only component that connects to M365 GCC is the **sync pipeline** (Durable Functions activities `collect_tenant_data` and `collect_compliance_data`), which uses **Microsoft Graph global endpoints**. The agent (Microsoft Foundry) does **not** connect to M365 GCC — it only reads from Azure AI Search and the HTTP API (SQL), which are populated by that Graph-based sync. Foundry is not used to connect back into M365 GCC.

## Endpoints

| Environment     | Login                          | Microsoft Graph              |
|----------------|---------------------------------|------------------------------|
| Commercial     | `https://login.microsoftonline.com` | `https://graph.microsoft.com` |
| **M365 GCC**   | `https://login.microsoftonline.com` | `https://graph.microsoft.com` |
| GCC High / DoD | `https://login.microsoftonline.us`  | `https://graph.microsoft.us`  |

So for **M365 GCC**:

- Use the **default** configuration (no `GRAPH_NATIONAL_CLOUD`).
- Register your app in your **GCC tenant’s** Entra ID (same as you would for any tenant).
- Onboard the GCC tenant in Compliance Advisor with that tenant’s app (client) ID and client secret.

Compliance Manager and Secure Score are available in M365 GCC and are reached via the same Graph endpoints as commercial.

---

## When to use GRAPH_NATIONAL_CLOUD=usgovernment

Set **GRAPH_NATIONAL_CLOUD=usgovernment** only if you are connecting to **GCC High** or **DoD** tenants, which use `login.microsoftonline.us` and `graph.microsoft.us`. For **M365 GCC** (standard), leave it unset.
