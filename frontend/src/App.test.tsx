import { describe, it, expect, vi, beforeEach } from "vitest";
import { render as plainRender } from "@testing-library/react";
import App from "./App";

describe("App", () => {
  beforeEach(() => {
    // App renders pages that call fetch with relative URLs which fail in jsdom
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({}),
      }),
    );
  });

  it("renders without crashing", () => {
    const { container } = plainRender(<App />);
    expect(container).toBeTruthy();
  });
});
