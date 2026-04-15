import React, { useEffect, useState } from "react";
import { getHealth } from "../../api/client";

interface HeaderProps {
  projectName: string;
  activeTab: string;
}

const Header: React.FC<HeaderProps> = ({ projectName, activeTab }) => {
  const [version, setVersion] = useState<string>("...");
  const [llmAvailable, setLlmAvailable] = useState<boolean>(false);
  const [reachable, setReachable] = useState<boolean>(false);

  useEffect(() => {
    getHealth()
      .then((h) => {
        setVersion(h.op3_version);
        setLlmAvailable(h.llm_available);
        setReachable(true);
      })
      .catch(() => setReachable(false));
  }, []);

  return (
    <header className="px-4 py-3 bg-op3-panel border-b border-gray-800
                       flex items-center justify-between">
      <div>
        <span className="text-sm font-semibold text-gray-100">{projectName}</span>
        <span className="text-xs text-gray-500 ml-3 capitalize">› {activeTab}</span>
      </div>
      <div className="flex items-center gap-3 text-xs">
        <span className="text-gray-500">op3 v{version}</span>
        <span className={
          "px-2 py-0.5 rounded " + (reachable
            ? "bg-op3-ok/20 text-op3-ok" : "bg-op3-danger/20 text-op3-danger")
        }>
          {reachable ? "backend ok" : "backend offline"}
        </span>
        <span className={
          "px-2 py-0.5 rounded " + (llmAvailable
            ? "bg-op3-accent/20 text-op3-accent" : "bg-gray-700 text-gray-400")
        }>
          {llmAvailable ? "AI ready" : "AI off"}
        </span>
      </div>
    </header>
  );
};

export default Header;
