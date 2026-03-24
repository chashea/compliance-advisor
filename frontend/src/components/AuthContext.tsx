import { PublicClientApplication, type Configuration } from "@azure/msal-browser";
import { MsalProvider } from "@azure/msal-react";
import type { ReactNode } from "react";

const clientId = import.meta.env.VITE_ENTRA_CLIENT_ID ?? "";
const tenantId = import.meta.env.VITE_ENTRA_TENANT_ID ?? "";

const msalConfig: Configuration = {
  auth: {
    clientId,
    authority: tenantId ? `https://login.microsoftonline.com/${tenantId}` : undefined,
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: "sessionStorage",
  },
};

const msalInstance = clientId ? new PublicClientApplication(msalConfig) : null;

export function AuthProvider({ children }: { children: ReactNode }) {
  if (!msalInstance) return <>{children}</>;
  return <MsalProvider instance={msalInstance}>{children}</MsalProvider>;
}

export { msalInstance };
