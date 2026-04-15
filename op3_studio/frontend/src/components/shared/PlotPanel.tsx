import React from "react";
import {
  CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
  ScatterChart, Scatter,
} from "recharts";

interface SeriesPoint {
  [key: string]: number | string;
}

interface PlotPanelProps {
  title?: string;
  data: SeriesPoint[];
  xKey: string;
  yKeys: { key: string; label?: string; color?: string }[];
  xLabel?: string;
  yLabel?: string;
  height?: number;
  type?: "line" | "scatter";
}

const COLORS = ["#58a6ff", "#3fb950", "#e3b341", "#ff7b72",
                "#bc8cff", "#79c0ff"];

const PlotPanel: React.FC<PlotPanelProps> = ({
  title, data, xKey, yKeys, xLabel, yLabel, height = 260, type = "line",
}) => (
  <div className="bg-op3-panel/60 border border-gray-800 rounded p-2">
    {title && (
      <div className="text-xs text-gray-400 mb-1">{title}</div>
    )}
    <ResponsiveContainer width="100%" height={height}>
      {type === "scatter" ? (
        <ScatterChart>
          <CartesianGrid stroke="#222" strokeDasharray="3 3" />
          <XAxis dataKey={xKey} type="number" stroke="#888"
                 label={xLabel ? { value: xLabel, position: "insideBottom",
                                   offset: -2, fill: "#888" } : undefined}
                 tick={{ fontSize: 10 }} />
          <YAxis stroke="#888"
                 label={yLabel ? { value: yLabel, angle: -90,
                                   position: "insideLeft", fill: "#888" }
                                 : undefined}
                 tick={{ fontSize: 10 }} />
          <Tooltip contentStyle={{ background: "#161b22",
                                   border: "1px solid #333" }} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {yKeys.map((y, i) => (
            <Scatter
              key={y.key}
              name={y.label || y.key}
              data={data}
              dataKey={y.key}
              fill={y.color || COLORS[i % COLORS.length]}
            />
          ))}
        </ScatterChart>
      ) : (
        <LineChart data={data}
                   margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
          <CartesianGrid stroke="#222" strokeDasharray="3 3" />
          <XAxis dataKey={xKey} stroke="#888"
                 label={xLabel ? { value: xLabel, position: "insideBottom",
                                   offset: -2, fill: "#888" } : undefined}
                 tick={{ fontSize: 10 }} />
          <YAxis stroke="#888"
                 label={yLabel ? { value: yLabel, angle: -90,
                                   position: "insideLeft", fill: "#888" }
                                 : undefined}
                 tick={{ fontSize: 10 }} />
          <Tooltip contentStyle={{ background: "#161b22",
                                   border: "1px solid #333",
                                   color: "#eee" }} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {yKeys.map((y, i) => (
            <Line
              key={y.key}
              type="monotone"
              dataKey={y.key}
              name={y.label || y.key}
              stroke={y.color || COLORS[i % COLORS.length]}
              strokeWidth={2}
              dot={false}
            />
          ))}
        </LineChart>
      )}
    </ResponsiveContainer>
  </div>
);

export default PlotPanel;
