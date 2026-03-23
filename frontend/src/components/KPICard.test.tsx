import { describe, it, expect } from "vitest";
import { render, screen } from "../test/render";
import KPICard from "./KPICard";

describe("KPICard", () => {
  it("renders value and label", () => {
    render(<KPICard icon={<span>IC</span>} value={42} label="Total Cases" />);
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("Total Cases")).toBeInTheDocument();
  });

  it("renders delta with up arrow", () => {
    render(<KPICard icon={<span>IC</span>} value={10} label="Alerts" delta="5%" deltaUp={true} />);
    expect(screen.getByText(/5%/)).toBeInTheDocument();
  });

  it("renders delta with down arrow", () => {
    render(<KPICard icon={<span>IC</span>} value={10} label="Alerts" delta="3%" deltaUp={false} />);
    expect(screen.getByText(/3%/)).toBeInTheDocument();
  });

  it("does not render delta when not provided", () => {
    render(<KPICard icon={<span>IC</span>} value={10} label="Alerts" />);
    expect(screen.queryByText(/↑|↓/)).not.toBeInTheDocument();
  });
});
