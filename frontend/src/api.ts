import type { CalendarItem, ChannelItem, DashboardData, NoteItem, SourceItem, UpdateResult } from "./types";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`请求失败：${response.status}`);
  return response.json() as Promise<T>;
}

export const api = {
  dashboard: () => getJson<DashboardData>("/api/dashboard"),
  sources: () => getJson<SourceItem[]>("/api/sources"),
  calendar: () => getJson<CalendarItem[]>("/api/calendar"),
  channels: () => getJson<ChannelItem[]>("/api/channels"),
  notes: () => getJson<NoteItem[]>("/api/notes"),
  checkUpdates: async () => {
    const response = await fetch("/api/updates/check", { method: "POST" });
    if (!response.ok) throw new Error("检查更新失败");
    return response.json() as Promise<UpdateResult>;
  },
  createNote: async (payload: { period: string; title: string; content: string; confidence: string }) => {
    const response = await fetch("/api/notes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error("保存失败");
    return response.json() as Promise<NoteItem>;
  }
};
