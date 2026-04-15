import React from "react";

interface UnitInputProps {
  label: string;
  value: number;
  unit: string;
  step?: number;
  min?: number;
  max?: number;
  onChange: (v: number) => void;
}

const UnitInput: React.FC<UnitInputProps> = ({
  label, value, unit, step = 0.1, min, max, onChange,
}) => (
  <label className="flex items-center justify-between gap-3 text-xs
                    text-gray-300 py-1">
    <span className="flex-1">{label}</span>
    <input
      type="number"
      value={Number.isFinite(value) ? value : 0}
      step={step}
      min={min}
      max={max}
      onChange={(e) => onChange(Number(e.target.value))}
      className="w-24 bg-gray-900 border border-gray-700 rounded
                 px-2 py-1 text-right font-mono text-gray-100
                 focus:outline-none focus:border-op3-accent"
    />
    <span className="w-12 text-gray-500 text-[10px]">{unit}</span>
  </label>
);

export default UnitInput;
