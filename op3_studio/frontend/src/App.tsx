import React, { useState } from "react";
import Sidebar, { TabKey } from "./components/layout/Sidebar";
import Header from "./components/layout/Header";

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabKey>("foundation");
  const [showChat, setShowChat] = useState(true);

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
            <div className="h-1/2 border-b border-gray-800
                            flex items-center justify-center text-gray-600">
              <span className="text-sm">3D viewer (Phase 3)</span>
            </div>
            <div className="h-1/2 overflow-y-auto p-4">
              <h2 className="text-base font-medium text-gray-200 mb-2">
                {activeTab.toUpperCase()} tab
              </h2>
              <p className="text-sm text-gray-500">
                Phase 1 skeleton -- tab content lands in Phase 4.
              </p>
            </div>
          </section>
          {showChat && (
            <aside className="w-96 bg-op3-panel border-l border-gray-800
                              flex items-center justify-center text-gray-600">
              <span className="text-sm">AI Chat (Phase 5)</span>
            </aside>
          )}
        </main>
      </div>
    </div>
  );
};

export default App;
