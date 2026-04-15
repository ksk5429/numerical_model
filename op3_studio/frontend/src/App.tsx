import React, { useEffect, useState } from "react";
import Sidebar, { TabKey } from "./components/layout/Sidebar";
import Header from "./components/layout/Header";
import SceneManager from "./components/three/SceneManager";
import ChatPanel from "./components/chat/ChatPanel";
import { getAnchorMesh, getFoundationMesh } from "./api/meshes";
import { useProject } from "./stores/projectStore";
import type { MeshResponse } from "./types/op3";

import SiteTab from "./components/tabs/SiteTab";
import FoundationTab from "./components/tabs/FoundationTab";
import AnalysisTab from "./components/tabs/AnalysisTab";
import ScourTab from "./components/tabs/ScourTab";
import ValidationTab from "./components/tabs/ValidationTab";
import AnchorTab from "./components/tabs/AnchorTab";
import DigitalTwinTab from "./components/tabs/DigitalTwinTab";
import ReportTab from "./components/tabs/ReportTab";

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabKey>("foundation");
  const [showChat, setShowChat] = useState(true);
  const [meshData, setMeshData] = useState<MeshResponse | null>(null);

  const { foundation, scourDepth, anchor } = useProject();

  // Refresh the 3D viewer when relevant inputs change.
  useEffect(() => {
    let cancelled = false;
    async function fetchMesh() {
      try {
        if (activeTab === "anchor") {
          const m = await getAnchorMesh(anchor);
          if (!cancelled) setMeshData(m);
        } else {
          const m = await getFoundationMesh(foundation, scourDepth);
          if (!cancelled) setMeshData(m);
        }
      } catch (e) {
        if (!cancelled) setMeshData(null);
      }
    }
    fetchMesh();
    return () => { cancelled = true; };
  }, [activeTab, foundation, scourDepth, anchor]);

  const tabs: Record<TabKey, React.ReactNode> = {
    site:       <SiteTab />,
    foundation: <FoundationTab />,
    analysis:   <AnalysisTab />,
    scour:      <ScourTab />,
    validation: <ValidationTab />,
    anchor:     <AnchorTab />,
    twin:       <DigitalTwinTab />,
    report:     <ReportTab />,
  };

  const projectStateForChat = {
    activeTab,
    foundation, scour_depth_m: scourDepth, anchor,
  };

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
            <div className="h-1/2 overflow-y-auto p-3">
              {tabs[activeTab]}
            </div>
          </section>
          {showChat && (
            <aside className="w-96">
              <ChatPanel projectState={projectStateForChat} />
            </aside>
          )}
        </main>
      </div>
    </div>
  );
};

export default App;
