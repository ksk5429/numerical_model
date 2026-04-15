import React from "react";
import ReactMarkdown from "react-markdown";
import CodeBlock from "./CodeBlock";
import ResultCard from "./ResultCard";
import type { ChatTurn } from "../../hooks/useChat";

const ChatMessage: React.FC<{ turn: ChatTurn }> = ({ turn }) => {
  const isUser = turn.role === "user";
  return (
    <div className={
      "rounded p-3 " +
      (isUser
        ? "bg-op3-accent/10 border border-op3-accent/30 ml-6"
        : "bg-gray-800/60 border border-gray-700 mr-6")
    }>
      <div className="text-[10px] uppercase tracking-wide
                      text-gray-500 mb-1">
        {isUser ? "you" : "op3 assistant"}
      </div>
      <div className="text-sm text-gray-100 prose prose-invert max-w-none
                      prose-p:my-1 prose-pre:my-1">
        <ReactMarkdown>{turn.content}</ReactMarkdown>
      </div>
      {turn.codeExecuted && turn.codeExecuted.length > 0 && (
        <div className="mt-2 space-y-1">
          <div className="text-[10px] text-gray-500">executed:</div>
          {turn.codeExecuted.map((c, i) => (
            <CodeBlock key={i} code={c} />
          ))}
        </div>
      )}
      {turn.results && turn.results.length > 0 && (
        <div className="mt-2">
          {turn.results.map((r, i) => (
            <ResultCard key={i} result={r} />
          ))}
        </div>
      )}
    </div>
  );
};

export default ChatMessage;
