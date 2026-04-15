// TypeScript counterparts of backend/models/schemas.py.
// Keep in sync when schemas.py changes.

export type SoilType = "sand" | "clay" | "silt" | "rock";

export interface SoilLayer {
  depth_m: number;
  thickness_m: number;
  soil_type: SoilType;
  undrained_shear_strength_kPa?: number | null;
  friction_angle_deg?: number | null;
  unit_weight_kN_m3: number;
  color?: string;
}

export interface SiteProfile {
  name: string;
  water_depth_m: number;
  layers: SoilLayer[];
  cpt_data?: any[] | null;
}

export type FoundationType =
  | "monopile" | "suction_bucket" | "tripod"
  | "jacket" | "suction_anchor";

export interface FoundationParams {
  type: FoundationType;
  diameter_m: number;
  length_m: number;
  wall_thickness_mm: number;
  foundation_mode:
    | "fixed" | "stiffness_6x6"
    | "distributed_bnwf" | "dissipation_weighted";
  standard: "dnv" | "api" | "iso" | "owa" | "pisa" | "hssmall";
}

export interface AnchorParams {
  diameter_m: number;
  skirt_length_m: number;
  wall_thickness_mm: number;
  padeye_depth_m?: number | null;
  padeye_offset_m?: number;
  submerged_weight_kN?: number;
}

export interface ClayProfile {
  su_mudline_kPa: number;
  su_gradient_kPa_per_m: number;
  gamma_eff_kN_per_m3?: number;
  sensitivity?: number;
  plasticity_index?: number;
}

// 3D mesh -- one component (cylinder, disc, line, etc.)
export interface MeshComponent {
  vertices?: number[][];
  faces?: number[][];
  normals?: number[][];
  colors?: number[][];
  type?: "line" | "water_plane";
  points?: number[][];
  color?: number[];
  linewidth?: number;
  extent?: number;
  y_offset?: number;
  opacity?: number;
}

export interface MeshResponse {
  components: Record<string, MeshComponent>;
  metadata?: Record<string, unknown>;
}

export interface CapacityResponse {
  vertical_kN: number;
  horizontal_kN: number;
  moment_kNm: number;
  natural_frequency_Hz?: number | null;
  safety_factor?: number | null;
  interaction_curve: { H: number; V: number }[];
  warnings: string[];
  metadata: Record<string, unknown>;
}

export interface AnchorCapacityResponse {
  method: string;
  H_ult_kN: number;
  V_ult_kN: number;
  T_ult_kN: number;
  load_angle_deg: number;
  interaction_envelope: { H_kN: number; V_kN: number }[];
  depth_profile: any[];
  metadata: Record<string, unknown>;
}

// Chat
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  reply: string;
  code_executed?: string[] | null;
  results?: any[] | null;
  error?: string | null;
}
