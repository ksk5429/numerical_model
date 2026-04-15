import { api } from "./client";
import type {
  AnchorParams, FoundationParams, MeshResponse,
} from "../types/op3";

export async function getFoundationMesh(
  foundation: FoundationParams,
  scour_depth_m: number,
  n_segments = 32,
  stress_profile: number[] | null = null,
): Promise<MeshResponse> {
  const r = await api.post("/api/foundation/mesh", {
    foundation, scour_depth_m, n_segments, stress_profile,
  });
  return r.data as MeshResponse;
}

export async function getAnchorMesh(
  anchor: AnchorParams,
  mooring_angle_deg = 35.0,
  mooring_length_m = 50.0,
  n_segments = 32,
): Promise<MeshResponse> {
  const r = await api.post("/api/anchor/mesh", {
    anchor, mooring_angle_deg, mooring_length_m, n_segments,
  });
  return r.data as MeshResponse;
}
