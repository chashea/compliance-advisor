import { describe, it, expect } from "vitest";
import { render, screen } from "../test/render";
import ScoreGauge from "./ScoreGauge";

describe("ScoreGauge", () => {
  it("renders percentage correctly", () => {
    render(<ScoreGauge score={80} max={100} />);
    // The percentage is shown in the SVG text element
    const allMatches = screen.getAllByText("80");
    expect(allMatches.length).toBeGreaterThanOrEqual(1);
  });

  it("renders 0 when max is 0", () => {
    render(<ScoreGauge score={0} max={0} />);
    const allMatches = screen.getAllByText("0");
    expect(allMatches.length).toBeGreaterThanOrEqual(1);
  });

  it("displays score and max points", () => {
    render(<ScoreGauge score={60} max={100} />);
    expect(screen.getByText(/100 pts/)).toBeInTheDocument();
  });

  it("renders custom label", () => {
    render(<ScoreGauge score={50} max={100} label="Data Score" />);
    expect(screen.getByText("Data Score")).toBeInTheDocument();
  });
});
