import { create } from "zustand";
import type {
  AnchorParams, ClayProfile, FoundationParams, SiteProfile, SoilLayer,
} from "../types/op3";

interface ProjectState {
  site: SiteProfile;
  foundation: FoundationParams;
  scourDepth: number;
  anchor: AnchorParams;
  anchorSoil: ClayProfile;

  // Setters
  setSite: (s: SiteProfile) => void;
  updateLayer: (i: number, patch: Partial<SoilLayer>) => void;
  addLayer: () => void;
  removeLayer: (i: number) => void;

  setFoundation: (f: Partial<FoundationParams>) => void;
  setScourDepth: (d: number) => void;

  setAnchor: (a: Partial<AnchorParams>) => void;
  setAnchorSoil: (s: Partial<ClayProfile>) => void;
}

export const useProject = create<ProjectState>((set) => ({
  site: {
    name: "Demo site",
    water_depth_m: 30.0,
    layers: [
      {
        depth_m: 0.0, thickness_m: 5.0, soil_type: "sand",
        friction_angle_deg: 32.0, unit_weight_kN_m3: 9.5,
        color: "#c2a878",
      },
      {
        depth_m: 5.0, thickness_m: 15.0, soil_type: "sand",
        friction_angle_deg: 35.0, unit_weight_kN_m3: 10.0,
        color: "#a8884f",
      },
    ],
  },
  foundation: {
    type: "suction_bucket",
    diameter_m: 8.0,
    length_m: 8.0,
    wall_thickness_mm: 25.0,
    foundation_mode: "stiffness_6x6",
    standard: "dnv",
  },
  scourDepth: 0.0,
  anchor: {
    diameter_m: 5.0,
    skirt_length_m: 15.0,
    wall_thickness_mm: 30.0,
    padeye_depth_m: 10.0,
    padeye_offset_m: 0.0,
    submerged_weight_kN: 250.0,
  },
  anchorSoil: {
    su_mudline_kPa: 5.0,
    su_gradient_kPa_per_m: 1.5,
    gamma_eff_kN_per_m3: 6.0,
    sensitivity: 3.0,
    plasticity_index: 27.0,
  },

  setSite: (s) => set({ site: s }),
  updateLayer: (i, patch) =>
    set((st) => {
      const layers = [...st.site.layers];
      layers[i] = { ...layers[i], ...patch };
      return { site: { ...st.site, layers } };
    }),
  addLayer: () =>
    set((st) => {
      const last = st.site.layers[st.site.layers.length - 1];
      const top = last ? last.depth_m + last.thickness_m : 0;
      return {
        site: {
          ...st.site,
          layers: [
            ...st.site.layers,
            {
              depth_m: top, thickness_m: 5.0, soil_type: "sand",
              friction_angle_deg: 32.0, unit_weight_kN_m3: 10.0,
              color: "#8b7355",
            },
          ],
        },
      };
    }),
  removeLayer: (i) =>
    set((st) => ({
      site: {
        ...st.site,
        layers: st.site.layers.filter((_, k) => k !== i),
      },
    })),

  setFoundation: (f) =>
    set((st) => ({ foundation: { ...st.foundation, ...f } })),
  setScourDepth: (d) => set({ scourDepth: d }),

  setAnchor: (a) => set((st) => ({ anchor: { ...st.anchor, ...a } })),
  setAnchorSoil: (s) =>
    set((st) => ({ anchorSoil: { ...st.anchorSoil, ...s } })),
}));
