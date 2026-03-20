import { useContext } from "react";
import { ThemeCtx } from "../contexts/ThemeCtx";

export function useTheme() {
  return useContext(ThemeCtx);
}
