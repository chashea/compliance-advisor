import { createContext } from "react";

export interface ThemeCtx {
  dark: boolean;
  toggleDark: () => void;
}

export const ThemeCtx = createContext<ThemeCtx>({ dark: false, toggleDark: () => {} });
