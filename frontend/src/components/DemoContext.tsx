import { useState, type ReactNode } from "react";
import { DemoCtx } from "../contexts/DemoCtx";

export function DemoProvider({ children }: { children: ReactNode }) {
  const [demo, setDemo] = useState(import.meta.env.VITE_DEMO === "true");
  return <DemoCtx.Provider value={{ demo, setDemo }}>{children}</DemoCtx.Provider>;
}
