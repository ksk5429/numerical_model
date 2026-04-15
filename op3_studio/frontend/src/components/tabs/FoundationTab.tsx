import React, { useEffect, useState } from "react";
import { useProject } from "../../stores/projectStore";
import UnitInput from "../shared/UnitInput";
import ParamSlider from "../shared/ParamSlider";
import LoadingOverlay from "../shared/LoadingOverlay";
import { postFoundationCapacity } from "../../api/analysis";
import type { CapacityResponse } from "../../types/op3";

const FOUNDATION_TYPES = [
  "monopile", "suction_bucket", "tripod", "jacket",
] as const;

const FoundationTab: React.FC = () => {
  const {
    site, foundation, scourDepth,
    setFoundation, setScourDepth,
  } = useProject();
  const [result, setResult] = useState<CapacityResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const compute = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await postFoundationCapacity(site, foundation, scourDepth);
      setResult(r);
    } catch (e: any) {
      setErr(e?.response?.data?.detail || e?.message || "request failed");
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { compute(); /* eslint-disable-next-line */ }, []);

  return (
    <div className="relative space-y-3">
      {busy && <LoadingOverlay />}

      <div className="grid grid-cols-2 gap-3">
        <div className="bg-op3-panel/60 border border-gray-800 rounded p-2">
          <h3 className="text-xs text-gray-400 uppercase mb-2">Geometry</h3>
          <label className="flex items-center justify-between gap-3 text-xs
                             text-gray-300 py-1">
            <span className="flex-1">Type</span>
            <select
              value={foundation.type}
              onChange={(e) => setFoundation(
                { type: e.target.value as any })}
              className="bg-gray-900 border border-gray-700 rounded px-2
                         py-1 text-xs"
            >
              {FOUNDATION_TYPES.map((t) =>
                <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <UnitInput
            label="Diameter D"
            value={foundation.diameter_m}
            unit="m" step={0.5}
            onChange={(v) => setFoundation({ diameter_m: v })}
          />
          <UnitInput
            label="Length L (skirt)"
            value={foundation.length_m}
            unit="m" step={0.5}
            onChange={(v) => setFoundation({ length_m: v })}
          />
          <UnitInput
            label="Wall thickness"
            value={foundation.wall_thickness_mm}
            unit="mm" step={5}
            onChange={(v) => setFoundation({ wall_thickness_mm: v })}
          />
          <ParamSlider
            label="Scour depth"
            value={scourDepth}
            min={0} max={4} step={0.1} unit="m"
            onChange={setScourDepth}
          />
          <button
            onClick={compute}
            className="mt-2 w-full bg-op3-accent/20 border border-op3-accent/40
                       text-op3-accent rounded py-1 text-xs"
          >Recalculate</button>
        </div>

        <div className="bg-op3-panel/60 border border-gray-800 rounded p-2">
          <h3 className="text-xs text-gray-400 uppercase mb-2">
            Capacity proxy (DNV-ST-0126)
          </h3>
          {err && <div className="text-xs text-op3-danger">{err}</div>}
          {result && (
            <div className="space-y-1 text-xs">
              <Stat label="Horizontal H" v={result.horizontal_kN} u="kN" />
              <Stat label="Vertical V"   v={result.vertical_kN}   u="kN" />
              <Stat label="Moment M"     v={result.moment_kNm}    u="kN·m" />
              <hr className="border-gray-800 my-1" />
              <div className="text-[11px] text-gray-500">
                K_xx = {fmtSci(result.metadata.Kxx_N_per_m)}
                {" N/m"}
              </div>
              <div className="text-[11px] text-gray-500">
                K_zz = {fmtSci(result.metadata.Kzz_N_per_m)}
                {" N/m"}
              </div>
              <div className="text-[11px] text-gray-500">
                K_φφ = {fmtSci(result.metadata.Kpp_Nm_per_rad)}
                {" Nm/rad"}
              </div>
              <div className="text-[11px] text-gray-600 mt-1">
                Method: {String(result.metadata.method)}
                <br />Soil: {String(result.metadata.soil_type)}
              </div>
              {result.warnings.length > 0 && (
                <div className="text-[11px] text-op3-warn mt-1">
                  ⚠ {result.warnings.join(" / ")}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const Stat: React.FC<{ label: string; v: number; u: string }> = ({
  label, v, u,
}) => (
  <div className="flex justify-between">
    <span className="text-gray-400">{label}</span>
    <span className="font-mono text-gray-100">
      {v.toLocaleString(undefined, { maximumFractionDigits: 1 })} {u}
    </span>
  </div>
);

function fmtSci(x: unknown) {
  const n = Number(x);
  if (!Number.isFinite(n)) return "-";
  return n.toExponential(2);
}

export default FoundationTab;
