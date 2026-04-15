import React, { useEffect, useState } from "react";
import { useProject } from "../../stores/projectStore";
import PlotPanel from "../shared/PlotPanel";
import LoadingOverlay from "../shared/LoadingOverlay";
import { postScourSweep, type ScourSweepResponse } from "../../api/analysis";

const ScourTab: React.FC = () => {
  const { site, foundation } = useProject();
  const [data, setData] = useState<ScourSweepResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [maxScour, setMaxScour] = useState(4.0);
  const [steps, setSteps] = useState(9);

  const compute = async () => {
    setBusy(true); setErr(null);
    try {
      const depths = Array.from({ length: steps },
        (_, i) => Number((i * maxScour / (steps - 1)).toFixed(2)));
      const r = await postScourSweep(site, foundation, depths);
      setData(r);
    } catch (e: any) {
      setErr(e?.response?.data?.detail || e?.message || "request failed");
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { compute(); /* eslint-disable-next-line */ }, []);

  const plotRows = data
    ? data.scour_depths_m.map((d, i) => ({
        depth_m: d,
        H_kN: data.H_ult_kN[i],
        V_kN: data.V_ult_kN[i],
        M_kNm: data.M_ult_kNm[i],
      }))
    : [];

  return (
    <div className="relative space-y-3">
      {busy && <LoadingOverlay message="Sweeping scour depths..." />}

      <div className="flex items-center gap-3 text-xs text-gray-300">
        <label>Max scour
          <input type="number" value={maxScour} step={0.5}
                 onChange={(e) => setMaxScour(Number(e.target.value))}
                 className="ml-2 w-16 bg-gray-900 border border-gray-700
                            rounded px-2 py-0.5 text-right" /> m
        </label>
        <label>Steps
          <input type="number" value={steps} step={1} min={3} max={20}
                 onChange={(e) => setSteps(Number(e.target.value))}
                 className="ml-2 w-16 bg-gray-900 border border-gray-700
                            rounded px-2 py-0.5 text-right" />
        </label>
        <button onClick={compute}
                className="ml-auto bg-op3-accent/20 border border-op3-accent/40
                           text-op3-accent rounded px-3 py-1">
          Run sweep
        </button>
      </div>

      {err && <div className="text-xs text-op3-danger">{err}</div>}

      {data && (
        <>
          <PlotPanel
            title={`Capacity vs scour for ${foundation.type}`}
            data={plotRows}
            xKey="depth_m"
            yKeys={[
              { key: "H_kN",  label: "H [kN]" },
              { key: "V_kN",  label: "V [kN]" },
              { key: "M_kNm", label: "M [kN·m]" },
            ]}
            xLabel="Scour depth [m]"
            height={260}
          />
          <div className="text-[11px] text-gray-500">
            Computed by /api/scour/sweep across {plotRows.length} depths
            (real op3 capacity calls per step).
          </div>
        </>
      )}
    </div>
  );
};

export default ScourTab;
