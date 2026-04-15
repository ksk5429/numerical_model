import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "/api",
  timeout: 60_000,
});

// Health probe used by the Header to show backend status.
export async function getHealth() {
  const r = await api.get("/api/health");
  return r.data as {
    status: string;
    op3_version: string;
    llm_available: boolean;
  };
}
