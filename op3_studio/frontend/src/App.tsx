import React, { useEffect, useState } from "react";
import Sidebar, { TabKey } from "./components/layout/Sidebar";
import Header from "./components/layout/Header";
import SceneManager from "./components/three/SceneManager";
import ChatPanel from "./components/chat/ChatPanel";
import { getAnchorMesh, getFoundationMesh } from "./api/meshes";
import type { MeshResponse } from "./types/op3";

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabKey>("foundation");
  const [showChat, setShowChat] = useState(true);
  const [meshData, setMeshData] = useState<MeshResponse | null>(null);
  const [scourDepth, setScourDepth] = useState(0);

  // Demo: fetch a default mesh per tab so the 3D view is never empty.
  useEffect(() => {
    let cancelled = false;
    async function fetchDemoMesh() {
      try {
        if (activeTab === "anchor") {
          const m = await getAnchorMesh({
            diameter_m: 5.0, skirt_length_m: 15.0,
            wall_thickness_mm: 30.0, padeye_depth_m: 10.0,
          });
          if (!cancelled) setMeshData(m);
        } else {
          const m = await getFoundationMesh(
            {
              type: activeTab === "foundation" ? "suction_bucket" :
                    activeTab === "twin"        ? "tripod" :
                                                  "suction_bucket",
              diameter_m: 8.0, length_m: 8.0,
              wall_thickness_mm: 25.0,
              foundation_mode: "stiffness_6x6", standard: "dnv",
            },
            scourDepth,
          );
          if (!cancelled) setMeshData(m);
        }
      } catch (err) {
        // Backend not running yet -- leave the viewer empty rather than
        // showing fake geometry.
        if (!cancelled) setMeshData(null);
      }
    }
    fetchDemoMesh();
    return () => { cancelled = true; };
  }, [activeTab, scourDepth]);

  return (
    <div className="flex h-screen bg-op3-bg text-gray-100">
      <Sidebar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onToggleChat={() => setShowChat(!showChat)}
      />
      <div className="flex-1 flex flex-col">
        <Header projectName="Op3 Studio" activeTab={activeTab} />
        <main className="flex-1 flex">
          <section className="flex-1 flex flex-col">
            <div className="h-1/2 border-b border-gray-800">
              <SceneManager meshData={meshData} />
            </div>
            <div className="h-1/2 overflow-y-auto p-4">
              <h2 className="text-base font-medium text-gray-200 mb-2">
                {activeTab.toUpperCase()} tab
              </h2>
              {activeTab === "foundation" && (
                <ScourSlider value={scourDepth} onChange={setScourDepth} />
              )}
              <p className="text-sm text-gray-500 mt-3">
                Phase 4 (full tab UIs) is deferred. The 3D viewer above is
                live: it talks to <code>/api/foundation/mesh</code> and
                <code> /api/anchor/mesh</code>.
              </p>
            </div>
          </section>
          {showChat && (
            <aside className="w-96">
              <ChatPanel projectState={{
                activeTab,
                scourDepth,
              }} />
            </aside>
          )}
        </main>
      </div>
    </div>
  );
};

const ScourSlider: React.FC<{
  value: number; onChange: (v: number) => void;
}> = ({ value, onChange }) => (
  <label className="block text-sm text-gray-300">
    Scour depth: <span className="text-op3-accent">{value.toFixed(2)} m</span>
    <input
      type="range" min={0} max={4} step={0.1}
      value={value} onChange={(e) => onChange(Number(e.target.value))}
      className="w-full mt-2"
    />
  </label>
);

export default App;
