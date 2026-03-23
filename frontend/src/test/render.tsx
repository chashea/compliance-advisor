import { render, type RenderOptions } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { DemoProvider } from "../components/DemoContext";
import { TenantProvider } from "../components/TenantContext";
import { ThemeProvider } from "../components/ThemeContext";
import type { ReactElement } from "react";

function AllProviders({ children }: { children: React.ReactNode }) {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <DemoProvider>
          <TenantProvider>{children}</TenantProvider>
        </DemoProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}

function customRender(ui: ReactElement, options?: Omit<RenderOptions, "wrapper">) {
  return render(ui, { wrapper: AllProviders, ...options });
}

export { customRender as render };
export { screen, fireEvent, waitFor, within, act } from "@testing-library/react";
export { default as userEvent } from "@testing-library/user-event";
