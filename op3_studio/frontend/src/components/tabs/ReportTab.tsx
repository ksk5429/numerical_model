import React, { useState } from "react";
import { useProject } from "../../stores/projectStore";
import { api } from "../../api/client";
import LoadingOverlay from "../shared/LoadingOverlay";
import ReactMarkdown from "react-markdown";
import { Download } from "lucide-react";

const ReportTab: React.FC = () => {
  const { site, foundation, scourDepth, anchor, anchorSoil } = useProject();
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const generate = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await api.post("/api/report/generate", {
        site, foundation, scour_depth_m: scourDepth,
        anchor, anchor_soil: anchorSoil,
      });
      setMarkdown(r.data.markdown);
    } catch (e: any) {
      setErr(e?.response?.data?.detail || e?.message || "request failed");
    } finally {
      setBusy(false);
    }
  };

  const download = () => {
    if (!markdown) return;
    const blob = new Blob([markdown], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `op3_report_${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="relative space-y-3">
      {busy && <LoadingOverlay message="Generating report..." />}
      <div className="flex items-center gap-3">
        <button
          onClick={generate}
          className="bg-op3-accent/20 border border-op3-accent/40
                     text-op3-accent rounded px-3 py-1 text-sm"
        >Generate report</button>
        {markdown && (
          <button
            onClick={download}
            className="bg-op3-ok/20 border border-op3-ok/40
                       text-op3-ok rounded px-3 py-1 text-sm
                       flex items-center gap-1"
          >
            <Download size={14} /> Download .md
          </button>
        )}
      </div>

      {err && <div className="text-xs text-op3-danger">{err}</div>}

      {markdown && (
        <div className="bg-op3-panel/60 border border-gray-800 rounded p-3
                        text-xs text-gray-200 prose prose-invert max-w-none
                        prose-headings:text-op3-accent prose-h1:text-base
                        prose-h2:text-sm prose-table:text-[11px]
                        max-h-[60vh] overflow-y-auto">
          <ReactMarkdown>{markdown}</ReactMarkdown>
        </div>
      )}
    </div>
  );
};

export default ReportTab;
