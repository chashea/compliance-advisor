import { useEffect, useState, type ReactNode } from "react";
import { ThemeCtx } from "../contexts/ThemeCtx";

function getInitial(): boolean {
  const stored = localStorage.getItem("theme");
  if (stored) return stored === "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [dark, setDark] = useState(getInitial);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  const toggleDark = () => setDark((d) => !d);

  return <ThemeCtx.Provider value={{ dark, toggleDark }}>{children}</ThemeCtx.Provider>;
}
