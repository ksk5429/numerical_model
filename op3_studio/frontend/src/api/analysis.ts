import { api } from "./client";
import type {
  AnchorCapacityResponse, AnchorParams, CapacityResponse, ClayProfile,
  FoundationParams, SiteProfile,
} from "../types/op3";

export interface ScourSweepResponse {
  scour_depths_m: number[];
  H_ult_kN: number[];
  V_ult_kN: number[];
  M_ult_kNm: number[];
  natural_frequency_Hz: number[] | null;
}

export interface InstallationResponse {
  self_weight_depth_m: number;
  max_suction_required_kPa: number;
  max_allowable_suction_kPa: number;
  plug_heave_ok: boolean;
  feasible: boolean;
  profile: { depth_m: number; F_drive_kN: number; F_resist_kN: number;
             s_req_kPa: number; s_allow_kPa: number; R_plug: number }[];
  metadata: Record<string, unknown>;
}

export async function postFoundationCapacity(
  site: SiteProfile, foundation: FoundationParams, scour_depth_m: number,
): Promise<CapacityResponse> {
  const r = await api.post("/api/foundation/capacity",
                           { site, foundation, scour_depth_m });
  return r.data;
}

export async function postScourSweep(
  site: SiteProfile, foundation: FoundationParams,
  scour_depths_m: number[],
): Promise<ScourSweepResponse> {
  const r = await api.post("/api/scour/sweep",
                           { site, foundation, scour_depths_m });
  return r.data;
}

export async function postAnchorCapacity(
  anchor: AnchorParams, soil: ClayProfile,
  method: string, load_angle_deg: number,
  aubeny_interface: "smooth" | "rough" = "rough",
): Promise<AnchorCapacityResponse> {
  const r = await api.post("/api/anchor/capacity", {
    anchor, soil, method, load_angle_deg, aubeny_interface,
  });
  return r.data;
}

export async function postAnchorInstallation(
  anchor: AnchorParams, soil: ClayProfile, water_depth_m: number,
): Promise<InstallationResponse> {
  const r = await api.post("/api/anchor/installation",
                           { anchor, soil, water_depth_m });
  return r.data;
}

export async function postOptimizePadeye(
  anchor: AnchorParams, soil: ClayProfile, method = "supachawarote_2005",
): Promise<{ optimal_padeye_depth_m: number;
             optimal_padeye_over_L: number; method: string }> {
  const r = await api.post("/api/anchor/optimize-padeye",
                           { anchor, soil, method });
  return r.data;
}
