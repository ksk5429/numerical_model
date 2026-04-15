import React from "react";

interface ParamSliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit?: string;
  onChange: (v: number) => void;
}

const ParamSlider: React.FC<ParamSliderProps> = ({
  label, value, min, max, step = 0.1, unit, onChange,
}) => (
  <label className="block text-xs text-gray-300 py-1">
    <div className="flex justify-between mb-1">
      <span>{label}</span>
      <span className="font-mono text-op3-accent">
        {value.toFixed(step < 1 ? 2 : 0)}{unit ? ` ${unit}` : ""}
      </span>
    </div>
    <input
      type="range"
      min={min} max={max} step={step}
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      className="w-full accent-op3-accent"
    />
  </label>
);

export default ParamSlider;
