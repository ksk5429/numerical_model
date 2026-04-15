import React from "react";

const CodeBlock: React.FC<{ code: string; lang?: string }> = ({
  code, lang = "python",
}) => (
  <pre className="bg-black/60 border border-gray-700 rounded p-2
                  text-xs text-gray-200 overflow-x-auto">
    <code className={`language-${lang}`}>{code}</code>
  </pre>
);

export default CodeBlock;
