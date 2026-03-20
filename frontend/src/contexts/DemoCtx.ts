import { createContext } from "react";

export interface DemoCtx {
  demo: boolean;
  setDemo: (d: boolean) => void;
}

export const DemoCtx = createContext<DemoCtx>({ demo: false, setDemo: () => {} });
