import { useCallback, useEffect, useState } from "react";
import { getChatInfo, sendChatMessage, type ChatInfo } from "../api/chat";
import type { ChatMessage, ChatResponse } from "../types/op3";

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
  codeExecuted?: string[];
  results?: any[];
  streaming?: boolean;
}

interface UseChatOptions {
  streaming?: boolean;
}

export function useChat(
  projectState: Record<string, unknown> = {},
  options: UseChatOptions = {},
) {
  const { streaming = true } = options;
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<ChatInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getChatInfo().then(setInfo).catch(() => setInfo(null));
  }, []);

  // ---- non-streaming (single round trip) -----------------------------
  const sendBlocking = useCallback(
    async (text: string, next: ChatTurn[]): Promise<ChatResponse | null> => {
      const history: ChatMessage[] = next.map((t) => ({
        role: t.role, content: t.content,
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
    },
    [projectState],
  );

  // ---- streaming (SSE) -----------------------------------------------
  const sendStreaming = useCallback(
    async (text: string, next: ChatTurn[]): Promise<void> => {
      const history: ChatMessage[] = next.slice(0, -1).map((t) => ({
        role: t.role, content: t.content,
      }));

      let firstBuffer = "";
      let secondBuffer = "";
      const exec: string[] = [];
      const results: any[] = [];

      // Append a placeholder assistant turn that we mutate as tokens arrive.
      const placeholder: ChatTurn = {
        role: "assistant", content: "", streaming: true,
      };
      setTurns([...next, placeholder]);

      const apiBase = (import.meta as any).env?.VITE_API_BASE
                      || "";
      const resp = await fetch(`${apiBase}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          conversation_history: history,
          project_state: projectState,
        }),
      });
      if (!resp.ok || !resp.body) {
        const detail = await resp.json().catch(() => null);
        throw new Error(detail?.detail || `stream failed ${resp.status}`);
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let leftover = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        leftover += decoder.decode(value, { stream: true });
        const events = leftover.split("\n\n");
        leftover = events.pop() || "";
        for (const ev of events) {
          if (!ev.startsWith("data: ")) continue;
          const payload = JSON.parse(ev.slice(6));
          switch (payload.type) {
            case "first_token":
              firstBuffer += payload.text;
              setTurns((cur) => updateLast(cur, {
                content: firstBuffer + secondBuffer,
              }));
              break;
            case "exec_start":
              exec[payload.i] = payload.code;
              setTurns((cur) => updateLast(cur, {
                codeExecuted: [...exec],
              }));
              break;
            case "exec_done":
              results[payload.i] = payload.result;
              setTurns((cur) => updateLast(cur, {
                results: [...results],
              }));
              break;
            case "second_token":
              secondBuffer += payload.text;
              setTurns((cur) => updateLast(cur, {
                content: secondBuffer || firstBuffer,
              }));
              break;
            case "done":
              setTurns((cur) => updateLast(cur, { streaming: false }));
              break;
            case "error":
              throw new Error(payload.message);
          }
        }
      }
    },
    [projectState],
  );

  const send = useCallback(
    async (text: string): Promise<ChatResponse | null> => {
      if (!text.trim()) return null;
      setError(null);
      setBusy(true);
      const next: ChatTurn[] = [
        ...turns,
        { role: "user", content: text },
      ];
      setTurns(next);
      try {
        if (streaming) {
          await sendStreaming(text, next);
          return null;  // streaming returns its data via setTurns
        }
        return await sendBlocking(text, next);
      } catch (e: any) {
        const msg = e?.response?.data?.detail || e?.message ||
                    "chat request failed";
        setError(msg);
        return null;
      } finally {
        setBusy(false);
      }
    },
    [turns, streaming, sendStreaming, sendBlocking],
  );

  return { turns, busy, info, error, send, setTurns };
}

function updateLast(turns: ChatTurn[], patch: Partial<ChatTurn>): ChatTurn[] {
  if (turns.length === 0) return turns;
  const out = [...turns];
  out[out.length - 1] = { ...out[out.length - 1], ...patch };
  return out;
}
