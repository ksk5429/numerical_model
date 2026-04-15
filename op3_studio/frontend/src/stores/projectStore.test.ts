import { describe, it, expect, beforeEach } from "vitest";
import { useProject } from "./projectStore";

describe("projectStore", () => {
  beforeEach(() => {
    // Reset to initial values by reloading the module is overkill;
    // we just take a fresh snapshot per test.
  });

  it("has sensible defaults", () => {
    const s = useProject.getState();
    expect(s.site.water_depth_m).toBeGreaterThan(0);
    expect(s.foundation.diameter_m).toBeGreaterThan(0);
    expect(s.anchor.diameter_m).toBeGreaterThan(0);
    expect(s.anchorSoil.su_mudline_kPa).toBeGreaterThanOrEqual(0);
  });

  it("setFoundation merges partial updates", () => {
    useProject.getState().setFoundation({ diameter_m: 12.0 });
    expect(useProject.getState().foundation.diameter_m).toBe(12.0);
  });

  it("addLayer appends a new soil layer at the bottom", () => {
    const before = useProject.getState().site.layers.length;
    useProject.getState().addLayer();
    expect(useProject.getState().site.layers.length).toBe(before + 1);
  });

  it("removeLayer removes the right index", () => {
    useProject.setState((s) => ({
      site: {
        ...s.site,
        layers: [
          { depth_m: 0, thickness_m: 1, soil_type: "sand",
            unit_weight_kN_m3: 10, color: "#000" },
          { depth_m: 1, thickness_m: 2, soil_type: "clay",
            unit_weight_kN_m3: 9, color: "#111" },
        ],
      },
    }));
    useProject.getState().removeLayer(0);
    const layers = useProject.getState().site.layers;
    expect(layers).toHaveLength(1);
    expect(layers[0].soil_type).toBe("clay");
  });
});
