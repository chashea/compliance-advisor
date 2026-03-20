import { useContext } from "react";
import { DemoCtx } from "../contexts/DemoCtx";

export function useDemo() {
  return useContext(DemoCtx);
}
