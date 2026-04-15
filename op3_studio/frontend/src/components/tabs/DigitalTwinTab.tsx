import React from "react";

const DigitalTwinTab: React.FC = () => (
  <div className="space-y-2 text-xs text-gray-300">
    <h3 className="text-gray-400 uppercase">Digital twin (Ch. 8)</h3>
    <p>
      The supervised encoder maps measured natural frequency
      <code> f₁ </code>(from OMA accelerometers) to posterior estimates
      of scour depth and soil stiffness via the 1,794-sample MC
      database.
    </p>
    <p className="text-gray-500">
      Encoder runtime is currently exposed via the AI Chat (
      <code>from op3.uq.encoder_bridge import predict</code>). A
      dedicated tab with sensor-data upload and posterior plots is
      planned for v1.1.
    </p>
  </div>
);

export default DigitalTwinTab;
