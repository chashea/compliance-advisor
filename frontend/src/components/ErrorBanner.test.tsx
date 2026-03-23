import { describe, it, expect } from "vitest";
import { render, screen } from "../test/render";
import ErrorBanner from "./ErrorBanner";

describe("ErrorBanner", () => {
  it("renders error message", () => {
    render(<ErrorBanner message="Something went wrong" />);
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });
});
