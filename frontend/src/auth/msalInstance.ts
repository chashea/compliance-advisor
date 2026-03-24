import { PublicClientApplication, type Configuration } from "@azure/msal-browser";

const clientId = import.meta.env.VITE_ENTRA_CLIENT_ID ?? "";
const tenantId = import.meta.env.VITE_ENTRA_TENANT_ID ?? "";

const msalConfig: Configuration = {
  auth: {
    clientId,
    authority: tenantId ? `https://login.microsoftonline.com/${tenantId}` : undefined,
    redirectUri: typeof window !== "undefined" ? window.location.origin : undefined,
  },
  cache: {
    cacheLocation: "sessionStorage",
  },
};

export const msalInstance = clientId ? new PublicClientApplication(msalConfig) : null;
