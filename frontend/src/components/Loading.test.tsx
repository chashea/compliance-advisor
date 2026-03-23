import { describe, it, expect } from "vitest";
import { render } from "../test/render";
import Loading from "./Loading";

describe("Loading", () => {
  it("renders spinner element", () => {
    const { container } = render(<Loading />);
    const spinner = container.querySelector(".animate-spin");
    expect(spinner).toBeInTheDocument();
  });
});
