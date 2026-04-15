import React from "react";

const LoadingOverlay: React.FC<{ message?: string }> = ({
  message = "Working...",
}) => (
  <div className="absolute inset-0 bg-black/50 flex items-center justify-center
                  z-10 backdrop-blur-sm">
    <div className="bg-op3-panel border border-gray-700 rounded p-4
                    flex items-center gap-3">
      <div className="w-4 h-4 border-2 border-op3-accent border-t-transparent
                      rounded-full animate-spin" />
      <span className="text-sm text-gray-200">{message}</span>
    </div>
  </div>
);

export default LoadingOverlay;
