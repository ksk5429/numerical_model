import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ParamSlider from "./ParamSlider";

describe("ParamSlider", () => {
  it("shows the current value with unit", () => {
    render(
      <ParamSlider label="Scour" value={1.5} min={0} max={4} unit="m"
                   onChange={() => {}} />,
    );
    expect(screen.getByText("Scour")).toBeInTheDocument();
    expect(screen.getByText(/1\.50 m/)).toBeInTheDocument();
  });

  it("calls onChange when slider moves", () => {
    const onChange = vi.fn();
    render(
      <ParamSlider label="x" value={0} min={0} max={5} step={1}
                   onChange={onChange} />,
    );
    const slider = screen.getByRole("slider");
    fireEvent.change(slider, { target: { value: "3" } });
    expect(onChange).toHaveBeenCalledWith(3);
  });
});
