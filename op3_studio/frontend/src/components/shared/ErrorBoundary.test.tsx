import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ErrorBoundary from "./ErrorBoundary";

const Boom: React.FC<{ explode?: boolean }> = ({ explode }) => {
  if (explode) throw new Error("kaboom");
  return <div>fine</div>;
};

describe("ErrorBoundary", () => {
  it("renders children when no error", () => {
    render(
      <ErrorBoundary>
        <Boom explode={false} />
      </ErrorBoundary>,
    );
    expect(screen.getByText("fine")).toBeInTheDocument();
  });

  it("renders fallback on error and shows Reset", () => {
    // Suppress React's scary console.error during this test
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <Boom explode />
      </ErrorBoundary>,
    );
    expect(screen.getByText(/Op3 Studio crashed/)).toBeInTheDocument();
    expect(screen.getByText("Reset")).toBeInTheDocument();
    errSpy.mockRestore();
  });

  it("Reset clears the error state (next render of children works)", () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const { rerender } = render(
      <ErrorBoundary>
        <Boom explode />
      </ErrorBoundary>,
    );
    fireEvent.click(screen.getByText("Reset"));
    rerender(
      <ErrorBoundary>
        <Boom explode={false} />
      </ErrorBoundary>,
    );
    expect(screen.getByText("fine")).toBeInTheDocument();
    errSpy.mockRestore();
  });
});
