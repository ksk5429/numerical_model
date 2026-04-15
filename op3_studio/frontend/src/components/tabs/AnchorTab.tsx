import React, { useEffect, useState } from "react";
import { useProject } from "../../stores/projectStore";
import UnitInput from "../shared/UnitInput";
import ParamSlider from "../shared/ParamSlider";
import PlotPanel from "../shared/PlotPanel";
import LoadingOverlay from "../shared/LoadingOverlay";
import {
  postAnchorCapacity, postAnchorInstallation, postOptimizePadeye,
} from "../../api/analysis";
import type { AnchorCapacityResponse } from "../../types/op3";
import type { InstallationResponse } from "../../api/analysis";

const METHODS = [
  "dnv_rp_e303", "murff_hamilton", "api_rp_2sk", "aubeny_2003",
] as const;

const AnchorTab: React.FC = () => {
  const {
    anchor, anchorSoil, site,
    setAnchor, setAnchorSoil,
  } = useProject();

  const [method, setMethod] = useState<typeof METHODS[number]>("dnv_rp_e303");
  const [angle, setAngle] = useState(30.0);
  const [cap, setCap] = useState<AnchorCapacityResponse | null>(null);
  const [inst, setInst] = useState<InstallationResponse | null>(null);
  const [zOpt, setZOpt] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const compute = async () => {
    setBusy(true); setErr(null);
    try {
      const [c, i, p] = await Promise.all([
        postAnchorCapacity(anchor, anchorSoil, method, angle),
        postAnchorInstallation(anchor, anchorSoil, site.water_depth_m),
        postOptimizePadeye(anchor, anchorSoil),
      ]);
      setCap(c); setInst(i); setZOpt(p.optimal_padeye_depth_m);
    } catch (e: any) {
      setErr(e?.response?.data?.detail || e?.message || "request failed");
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { compute(); /* eslint-disable-next-line */ }, []);

  return (
    <div className="relative space-y-3">
      {busy && <LoadingOverlay message="Computing capacity + installation..." />}

      <div className="grid grid-cols-3 gap-3">
        <div className="bg-op3-panel/60 border border-gray-800 rounded p-2">
          <h3 className="text-xs text-gray-400 uppercase mb-2">Anchor</h3>
          <UnitInput label="Diameter D" value={anchor.diameter_m} unit="m"
                     step={0.5}
                     onChange={(v) => setAnchor({ diameter_m: v })} />
          <UnitInput label="Skirt L" value={anchor.skirt_length_m} unit="m"
                     step={0.5}
                     onChange={(v) => setAnchor({ skirt_length_m: v })} />
          <UnitInput label="Wall t" value={anchor.wall_thickness_mm} unit="mm"
                     step={5}
                     onChange={(v) => setAnchor({ wall_thickness_mm: v })} />
          <UnitInput label="Padeye z_p"
                     value={anchor.padeye_depth_m ?? 0} unit="m" step={0.5}
                     onChange={(v) => setAnchor({ padeye_depth_m: v })} />
          <UnitInput label="W' submerged"
                     value={anchor.submerged_weight_kN ?? 0} unit="kN" step={50}
                     onChange={(v) => setAnchor({ submerged_weight_kN: v })} />
        </div>

        <div className="bg-op3-panel/60 border border-gray-800 rounded p-2">
          <h3 className="text-xs text-gray-400 uppercase mb-2">Clay profile</h3>
          <UnitInput label="su mudline"
                     value={anchorSoil.su_mudline_kPa} unit="kPa" step={1}
                     onChange={(v) => setAnchorSoil({ su_mudline_kPa: v })} />
          <UnitInput label="su gradient"
                     value={anchorSoil.su_gradient_kPa_per_m}
                     unit="kPa/m" step={0.1}
                     onChange={(v) => setAnchorSoil(
                       { su_gradient_kPa_per_m: v })} />
          <UnitInput label="γ' eff"
                     value={anchorSoil.gamma_eff_kN_per_m3 ?? 6} unit="kN/m³"
                     step={0.5}
                     onChange={(v) => setAnchorSoil(
                       { gamma_eff_kN_per_m3: v })} />
          <UnitInput label="Sensitivity St"
                     value={anchorSoil.sensitivity ?? 3} unit=""
                     step={0.5}
                     onChange={(v) => setAnchorSoil({ sensitivity: v })} />
          <UnitInput label="PI"
                     value={anchorSoil.plasticity_index ?? 27} unit="%"
                     step={1}
                     onChange={(v) => setAnchorSoil(
                       { plasticity_index: v })} />
        </div>

        <div className="bg-op3-panel/60 border border-gray-800 rounded p-2">
          <h3 className="text-xs text-gray-400 uppercase mb-2">
            Capacity method
          </h3>
          <label className="flex items-center justify-between gap-3 text-xs
                             text-gray-300 py-1">
            <span className="flex-1">Method</span>
            <select value={method}
                    onChange={(e) => setMethod(e.target.value as any)}
                    className="bg-gray-900 border border-gray-700 rounded
                               px-2 py-1 text-xs">
              {METHODS.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </label>
          <ParamSlider label="Load angle θ" value={angle}
                       min={0} max={90} step={1} unit="°"
                       onChange={setAngle} />
          <button onClick={compute}
                  className="mt-2 w-full bg-op3-accent/20
                             border border-op3-accent/40
                             text-op3-accent rounded py-1 text-xs">
            Recalculate
          </button>

          {cap && (
            <div className="mt-2 text-xs space-y-1">
              <Row k="H_ult" v={cap.H_ult_kN} u="kN" />
              <Row k="V_ult" v={cap.V_ult_kN} u="kN" />
              <Row k="T_ult" v={cap.T_ult_kN} u="kN" />
            </div>
          )}
        </div>
      </div>

      {err && <div className="text-xs text-op3-danger">{err}</div>}

      {cap && (
        <PlotPanel
          title="V–H interaction envelope"
          data={cap.interaction_envelope.map((p) => ({
            H_kN: p.H_kN, V_kN: p.V_kN,
          }))}
          xKey="H_kN"
          yKeys={[{ key: "V_kN", label: "V [kN]", color: "#58a6ff" }]}
          xLabel="H [kN]"
          yLabel="V [kN]"
          height={220}
        />
      )}

      {inst && (
        <div className="bg-op3-panel/60 border border-gray-800 rounded p-2">
          <h3 className="text-xs text-gray-400 uppercase mb-2">
            Installation feasibility
          </h3>
          <div className="grid grid-cols-2 gap-2 text-xs mb-2">
            <Row k="Self-weight depth"
                 v={inst.self_weight_depth_m} u="m" />
            <Row k="Max suction required"
                 v={inst.max_suction_required_kPa} u="kPa" />
            <Row k="Cavitation limit"
                 v={inst.max_allowable_suction_kPa} u="kPa" />
            <div>
              <span className="text-gray-400">Verdict: </span>
              <span className={inst.feasible
                ? "text-op3-ok" : "text-op3-danger"}>
                {inst.feasible ? "FEASIBLE" : "INFEASIBLE"}
              </span>
              {" / "}
              <span className={inst.plug_heave_ok
                ? "text-op3-ok" : "text-op3-warn"}>
                plug {inst.plug_heave_ok ? "ok" : "heave!"}
              </span>
            </div>
          </div>
          <PlotPanel
            data={inst.profile.map((p) => ({
              depth_m: p.depth_m,
              s_req: p.s_req_kPa,
              s_allow: p.s_allow_kPa,
            }))}
            xKey="depth_m"
            yKeys={[
              { key: "s_req",   label: "Required [kPa]",   color: "#ff7b72" },
              { key: "s_allow", label: "Cavitation [kPa]", color: "#3fb950" },
            ]}
            xLabel="Depth [m]"
            height={180}
          />
        </div>
      )}

      {zOpt !== null && (
        <div className="text-xs text-gray-400 italic">
          Optimal padeye (Supachawarote 2005): z_p* ={" "}
          <span className="text-op3-accent">{zOpt.toFixed(2)} m</span>
          {" "}({(zOpt / anchor.skirt_length_m * 100).toFixed(0)}% of L)
        </div>
      )}
    </div>
  );
};

const Row: React.FC<{ k: string; v: number; u: string }> = ({ k, v, u }) => (
  <div className="flex justify-between">
    <span className="text-gray-400">{k}</span>
    <span className="font-mono text-gray-100">
      {v.toLocaleString(undefined, { maximumFractionDigits: 1 })} {u}
    </span>
  </div>
);

export default AnchorTab;
