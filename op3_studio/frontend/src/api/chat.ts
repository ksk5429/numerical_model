import { api } from "./client";
import type { ChatMessage, ChatResponse } from "../types/op3";

export interface ChatInfo {
  model: string;
  available: boolean;
  max_tokens: number;
}

export async function getChatInfo(): Promise<ChatInfo> {
  const r = await api.get("/api/chat/info");
  return r.data as ChatInfo;
}

export async function sendChatMessage(
  message: string,
  conversation_history: ChatMessage[],
  project_state: Record<string, unknown> = {},
): Promise<ChatResponse> {
  const r = await api.post("/api/chat/message", {
    message, conversation_history, project_state,
  });
  return r.data as ChatResponse;
}
