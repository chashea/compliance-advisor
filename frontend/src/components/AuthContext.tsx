import { MsalProvider } from "@azure/msal-react";
import type { ReactNode } from "react";
import { msalInstance } from "../auth/msalInstance";

export function AuthProvider({ children }: { children: ReactNode }) {
  if (!msalInstance) return <>{children}</>;
  return <MsalProvider instance={msalInstance}>{children}</MsalProvider>;
}
