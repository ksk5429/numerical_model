import React, { useEffect, useState } from "react";
import { api } from "../../api/client";

const AnalysisTab: React.FC = () => {
  const [jobs, setJobs] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.get("/api/analysis/jobs")
      .then((r) => setJobs(r.data))
      .catch((e) => setErr(e.message));
  }, []);

  return (
    <div className="space-y-3">
      <h3 className="text-xs text-gray-400 uppercase">Analysis jobs</h3>
      {err && <div className="text-xs text-op3-danger">{err}</div>}
      {jobs.length === 0 && (
        <p className="text-xs text-gray-500">
          No long-running jobs yet. The backend's
          <code> /api/analysis/jobs </code>endpoint is wired but
          job orchestration (eigenvalue, pushover, OpenFAST coupling)
          is queued for a future release. For now use the AI Chat to
          run interactive op3 calculations.
        </p>
      )}
    </div>
  );
};

export default AnalysisTab;
