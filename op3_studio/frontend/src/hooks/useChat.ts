import { useCallback, useEffect, useState } from "react";
import { getChatInfo, sendChatMessage, type ChatInfo } from "../api/chat";
import type { ChatMessage, ChatResponse } from "../types/op3";

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
  codeExecuted?: string[];
  results?: any[];
}

export function useChat(projectState: Record<string, unknown> = {}) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<ChatInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getChatInfo().then(setInfo).catch(() => setInfo(null));
  }, []);

  const send = useCallback(
    async (text: string): Promise<ChatResponse | null> => {
      if (!text.trim()) return null;
      setError(null);
      setBusy(true);
      const next = [...turns, { role: "user" as const, content: text }];
      setTurns(next);
      try {
        const history: ChatMessage[] = next.map((t) => ({
          role: t.role,
          content: t.content,
        }));
        const resp = await sendChatMessage(text, history.slice(0, -1),
                                           projectState);
        setTurns([
          ...next,
          {
            role: "assistant",
            content: resp.reply,
            codeExecuted: resp.code_executed || undefined,
            results: resp.results || undefined,
          },
        ]);
        return resp;
      } catch (e: any) {
        const msg = e?.response?.data?.detail || e?.message ||
                    "chat request failed";
        setError(msg);
        return null;
      } finally {
        setBusy(false);
      }
    },
    [turns, projectState],
  );

  return { turns, busy, info, error, send, setTurns };
}
