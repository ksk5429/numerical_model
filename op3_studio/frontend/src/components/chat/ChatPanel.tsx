import React, { useEffect, useRef } from "react";
import ChatMessage from "./ChatMessage";
import ChatInput from "./ChatInput";
import { useChat } from "../../hooks/useChat";

const SUGGESTIONS = [
  "Calculate capacity of a 6 m suction bucket in dense sand",
  "세굴 2미터일 때 안전한가?",
  "Run an anchor capacity check at 30° load angle",
  "Compare DNV vs API for L/D = 3 anchor",
];

interface ChatPanelProps {
  projectState?: Record<string, unknown>;
}

const ChatPanel: React.FC<ChatPanelProps> = ({ projectState = {} }) => {
  const { turns, busy, info, error, send } = useChat(projectState);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, busy]);

  return (
    <div className="flex flex-col h-full bg-op3-panel border-l border-gray-800">
      <div className="px-3 py-2 border-b border-gray-800 flex items-center gap-2">
        <span className={
          "w-2 h-2 rounded-full " +
          (info?.available ? "bg-op3-ok animate-pulse" : "bg-gray-600")
        } />
        <span className="text-sm font-medium text-gray-200">
          Op3 AI Assistant
        </span>
        <span className="text-xs text-gray-500 ml-auto">
          {info?.model || "..."}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
        {turns.length === 0 && (
          <div className="text-center text-gray-500 mt-6">
            <div className="text-3xl mb-3">🌊</div>
            <p className="text-xs">
              Ask anything about offshore foundation design.
            </p>
            {!info?.available && (
              <p className="text-xs mt-3 text-op3-warn">
                Set ANTHROPIC_API_KEY in op3_studio/.env to enable chat.
              </p>
            )}
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  disabled={!info?.available || busy}
                  className="text-[11px] px-2 py-1 rounded-full
                             bg-gray-800 text-gray-300 border border-gray-700
                             hover:bg-gray-700 disabled:opacity-50"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((t, i) => <ChatMessage key={i} turn={t} />)}

        {busy && (
          <div className="flex items-center gap-2 text-gray-500">
            <span className="w-1.5 h-1.5 bg-op3-accent rounded-full
                             animate-bounce [animation-delay:0ms]" />
            <span className="w-1.5 h-1.5 bg-op3-accent rounded-full
                             animate-bounce [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 bg-op3-accent rounded-full
                             animate-bounce [animation-delay:300ms]" />
            <span className="text-xs">analyzing...</span>
          </div>
        )}

        {error && (
          <div className="text-xs text-op3-danger bg-op3-danger/10 p-2
                          rounded border border-op3-danger/40">
            {error}
          </div>
        )}

        <div ref={endRef} />
      </div>

      <ChatInput
        onSend={send}
        disabled={busy || !info?.available}
        placeholder={info?.available
          ? "Ask about foundation design... (한국어 가능)"
          : "Set ANTHROPIC_API_KEY to enable chat"}
      />
    </div>
  );
};

export default ChatPanel;
