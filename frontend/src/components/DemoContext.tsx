import { createContext, useContext, useState, type ReactNode } from "react";

interface DemoCtx {
  demo: boolean;
  setDemo: (d: boolean) => void;
}

const Ctx = createContext<DemoCtx>({ demo: false, setDemo: () => {} });

export function DemoProvider({ children }: { children: ReactNode }) {
  const [demo, setDemo] = useState(import.meta.env.VITE_DEMO === "true");
  return <Ctx.Provider value={{ demo, setDemo }}>{children}</Ctx.Provider>;
}

export function useDemo() {
  return useContext(Ctx);
}
