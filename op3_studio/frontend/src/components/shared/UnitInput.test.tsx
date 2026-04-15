import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import UnitInput from "./UnitInput";

describe("UnitInput", () => {
  it("renders label, value, and unit", () => {
    render(
      <UnitInput label="Diameter" value={5.0} unit="m"
                 onChange={() => {}} />,
    );
    expect(screen.getByText("Diameter")).toBeInTheDocument();
    expect(screen.getByText("m")).toBeInTheDocument();
    expect(screen.getByDisplayValue("5")).toBeInTheDocument();
  });

  it("calls onChange with a number", () => {
    const onChange = vi.fn();
    render(
      <UnitInput label="L" value={1.0} unit="m" onChange={onChange} />,
    );
    fireEvent.change(screen.getByDisplayValue("1"),
                     { target: { value: "2.5" } });
    expect(onChange).toHaveBeenCalledWith(2.5);
  });

  it("renders 0 when value is NaN", () => {
    render(
      <UnitInput label="x" value={NaN} unit="m" onChange={() => {}} />,
    );
    expect(screen.getByDisplayValue("0")).toBeInTheDocument();
  });
});
