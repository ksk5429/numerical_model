import React from "react";
import { useProject } from "../../stores/projectStore";
import DataTable from "../shared/DataTable";
import UnitInput from "../shared/UnitInput";
import PlotPanel from "../shared/PlotPanel";

const SiteTab: React.FC = () => {
  const {
    site, updateLayer, addLayer, removeLayer, setSite,
  } = useProject();

  // su / depth profile for plotting (linear interp from layer entries)
  const profile = site.layers.map((L) => ({
    depth_m: L.depth_m + L.thickness_m / 2,
    su_kPa: L.undrained_shear_strength_kPa ?? 0,
    phi_deg: L.friction_angle_deg ?? 0,
  }));

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <input
          value={site.name}
          onChange={(e) => setSite({ ...site, name: e.target.value })}
          className="flex-1 bg-gray-900 border border-gray-700 rounded
                     px-2 py-1 text-sm text-gray-100"
        />
        <UnitInput
          label="Water depth"
          value={site.water_depth_m}
          unit="m"
          step={1}
          onChange={(v) => setSite({ ...site, water_depth_m: v })}
        />
      </div>

      <div className="bg-op3-panel/60 border border-gray-800 rounded p-2">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-xs text-gray-400 uppercase">Soil layers</h3>
          <button
            onClick={addLayer}
            className="text-xs px-2 py-0.5 bg-op3-accent/20
                       text-op3-accent rounded border border-op3-accent/40"
          >+ layer</button>
        </div>
        <DataTable
          columns={[
            { key: "depth_m", header: "Top [m]", align: "right",
              render: (r, i) => (
                <input type="number" value={r.depth_m} step={0.1}
                       onChange={(e) => updateLayer(i,
                         { depth_m: Number(e.target.value) })}
                       className="w-16 bg-gray-900 rounded border border-gray-700
                                  px-1 text-right" />
              ) },
            { key: "thickness_m", header: "h [m]", align: "right",
              render: (r, i) => (
                <input type="number" value={r.thickness_m} step={0.1}
                       onChange={(e) => updateLayer(i,
                         { thickness_m: Number(e.target.value) })}
                       className="w-16 bg-gray-900 rounded border border-gray-700
                                  px-1 text-right" />
              ) },
            { key: "soil_type", header: "Type",
              render: (r, i) => (
                <select value={r.soil_type}
                        onChange={(e) => updateLayer(i,
                          { soil_type: e.target.value as any })}
                        className="bg-gray-900 rounded border border-gray-700
                                   px-1 text-xs">
                  {["sand", "clay", "silt", "rock"].map((t) =>
                    <option key={t} value={t}>{t}</option>)}
                </select>
              ) },
            { key: "friction_angle_deg", header: "φ [°]", align: "right",
              render: (r, i) => (
                <input type="number" value={r.friction_angle_deg ?? 0}
                       step={1}
                       onChange={(e) => updateLayer(i,
                         { friction_angle_deg: Number(e.target.value) })}
                       className="w-14 bg-gray-900 rounded border border-gray-700
                                  px-1 text-right" />
              ) },
            { key: "undrained_shear_strength_kPa", header: "su [kPa]",
              align: "right",
              render: (r, i) => (
                <input type="number"
                       value={r.undrained_shear_strength_kPa ?? 0}
                       step={1}
                       onChange={(e) => updateLayer(i,
                         { undrained_shear_strength_kPa:
                             Number(e.target.value) })}
                       className="w-16 bg-gray-900 rounded border border-gray-700
                                  px-1 text-right" />
              ) },
            { key: "unit_weight_kN_m3", header: "γ' [kN/m³]", align: "right",
              render: (r, i) => (
                <input type="number" value={r.unit_weight_kN_m3} step={0.1}
                       onChange={(e) => updateLayer(i,
                         { unit_weight_kN_m3: Number(e.target.value) })}
                       className="w-16 bg-gray-900 rounded border border-gray-700
                                  px-1 text-right" />
              ) },
          ]}
          rows={site.layers}
          onDelete={removeLayer}
        />
      </div>

      <PlotPanel
        title="Strength profile vs depth"
        data={profile}
        xKey="depth_m"
        yKeys={[
          { key: "su_kPa", label: "su [kPa]", color: "#58a6ff" },
          { key: "phi_deg", label: "φ [°]", color: "#3fb950" },
        ]}
        xLabel="Depth [m]"
        height={180}
      />
    </div>
  );
};

export default SiteTab;
