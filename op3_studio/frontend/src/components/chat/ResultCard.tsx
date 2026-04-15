import React from "react";

interface ExecutionLike {
  success: boolean;
  stdout?: string;
  results?: Record<string, unknown>;
  error?: string | null;
  error_type?: string | null;
}

const ResultCard: React.FC<{ result: ExecutionLike }> = ({ result }) => {
  const ok = result.success;
  return (
    <div className={
      "rounded border text-xs p-2 mt-1 " +
      (ok ? "border-op3-ok/40 bg-op3-ok/5"
          : "border-op3-danger/40 bg-op3-danger/5")
    }>
      <div className={"font-medium mb-1 " +
                      (ok ? "text-op3-ok" : "text-op3-danger")}>
        {ok ? "OK" : `${result.error_type || "Error"}: ${result.error}`}
      </div>
      {result.stdout && result.stdout.trim() && (
        <pre className="text-gray-300 whitespace-pre-wrap mt-1">
          {result.stdout.trim()}
        </pre>
      )}
      {result.results && Object.keys(result.results).length > 0 && (
        <div className="mt-1">
          <div className="text-gray-400 mb-1">vars:</div>
          <pre className="text-gray-200 text-[10px]">
            {JSON.stringify(result.results, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};

export default ResultCard;
