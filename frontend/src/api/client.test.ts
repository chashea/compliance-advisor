import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../auth/msalInstance", () => ({
  msalInstance: null,
}));

vi.mock("../demo/data", () => ({
  getDemoData: (endpoint: string) => ({ demo: true, endpoint }),
}));

describe("post()", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("calls fetch and returns JSON on success", async () => {
    const { post } = await import("./client");
    const mockData = { status: "ok" };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockData),
      }),
    );
    const result = await post("status");
    expect(result).toEqual(mockData);
    expect(fetch).toHaveBeenCalledWith("/api/advisor/status", expect.objectContaining({ method: "POST" }));
  });

  it("throws on non-ok response", async () => {
    const { post } = await import("./client");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: () => Promise.resolve({ error: "server error" }),
      }),
    );
    await expect(post("status")).rejects.toThrow("server error");
  });

  it("throws with statusText when JSON parse fails", async () => {
    const { post } = await import("./client");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: () => Promise.reject(new Error("parse fail")),
      }),
    );
    await expect(post("status")).rejects.toThrow("Internal Server Error");
  });

  it("sends body as JSON", async () => {
    const { post } = await import("./client");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({}),
      }),
    );
    await post("overview", { department: "IT" });
    expect(fetch).toHaveBeenCalledWith(
      "/api/advisor/overview",
      expect.objectContaining({
        body: JSON.stringify({ department: "IT" }),
      }),
    );
  });

  it("returns demo data when demo flag is true", async () => {
    const { post } = await import("./client");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const result = await post("status", undefined, true);
    expect(result).toEqual({ demo: true, endpoint: "status" });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
