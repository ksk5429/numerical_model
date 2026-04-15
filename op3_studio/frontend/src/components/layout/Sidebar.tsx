import React from "react";
import {
  Layers, HardDrive, Activity, Waves, ShieldCheck,
  Anchor, Cpu, FileText, MessageSquare,
} from "lucide-react";

export type TabKey =
  | "site" | "foundation" | "analysis" | "scour"
  | "validation" | "anchor" | "twin" | "report";

interface SidebarProps {
  activeTab: TabKey;
  onTabChange: (tab: TabKey) => void;
  onToggleChat: () => void;
}

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: "site",       label: "Site & Soil",     icon: <Layers size={18} /> },
  { key: "foundation", label: "Foundation",      icon: <HardDrive size={18} /> },
  { key: "analysis",   label: "Analysis",        icon: <Activity size={18} /> },
  { key: "scour",      label: "Scour",           icon: <Waves size={18} /> },
  { key: "validation", label: "V&V",             icon: <ShieldCheck size={18} /> },
  { key: "anchor",     label: "Anchor",          icon: <Anchor size={18} /> },
  { key: "twin",       label: "Digital Twin",    icon: <Cpu size={18} /> },
  { key: "report",     label: "Report",          icon: <FileText size={18} /> },
];

const Sidebar: React.FC<SidebarProps> = ({
  activeTab, onTabChange, onToggleChat,
}) => (
  <aside className="w-56 bg-op3-panel border-r border-gray-800 flex flex-col">
    <div className="px-4 py-4 border-b border-gray-800">
      <h1 className="text-lg font-semibold text-op3-accent">Op3 Studio</h1>
      <p className="text-xs text-gray-500 mt-1">Offshore foundation analysis</p>
    </div>
    <nav className="flex-1 overflow-y-auto py-2">
      {TABS.map((t) => (
        <button
          key={t.key}
          onClick={() => onTabChange(t.key)}
          className={
            "w-full text-left px-4 py-2 flex items-center gap-3 text-sm " +
            (activeTab === t.key
              ? "bg-op3-accent/10 text-op3-accent border-l-2 border-op3-accent"
              : "text-gray-300 hover:bg-gray-800")
          }
        >
          {t.icon}
          {t.label}
        </button>
      ))}
    </nav>
    <button
      onClick={onToggleChat}
      className="mx-3 mb-3 mt-2 px-3 py-2 rounded bg-gray-800 text-gray-200
                 hover:bg-gray-700 flex items-center gap-2 text-sm"
    >
      <MessageSquare size={16} />
      Toggle AI Chat
    </button>
  </aside>
);

export default Sidebar;
