import React from "react";

const ValidationTab: React.FC = () => (
  <div className="space-y-2 text-xs text-gray-300">
    <h3 className="text-gray-400 uppercase">V&amp;V dashboard</h3>
    <p>
      Op³ ships <strong>39 cross-validation benchmarks</strong> against
      25+ published sources (35/38 in-scope verified, 92%). The full
      report lives at{" "}
      <code>validation/cross_validations/VV_REPORT.md</code> in the
      repository root.
    </p>
    <p className="text-gray-500">
      Anchor module benchmarks (Aubeny 2003 N_p table, Randolph &amp;
      House 2002 trend, API/DNV cut-off, closed-form linear integral)
      live under <code>tests/test_anchors/test_anchor_benchmarks.py</code>:
      <strong className="text-op3-ok"> 134/134 passing</strong>.
    </p>
    <p className="text-gray-500">
      The Studio backend itself is covered by 55 tests (health,
      mesh, op3 bridge, sandbox).
    </p>
  </div>
);

export default ValidationTab;
