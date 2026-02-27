/**
 * Kairo API Client — typed wrapper for all backend endpoints
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getHeaders(): HeadersInit {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("kairo_token");
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { ...getHeaders(), ...(options.headers || {}) },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Auth ──

export const auth = {
  register: (data: { email: string; username: string; password: string; full_name?: string; preferred_language?: string }) =>
    request<{ access_token: string; user: any }>("/api/auth/register", { method: "POST", body: JSON.stringify(data) }),

  login: (data: { email: string; password: string }) =>
    request<{ access_token: string; user: any }>("/api/auth/login", { method: "POST", body: JSON.stringify(data) }),

  me: () => request<any>("/api/auth/me"),

  updateProfile: (data: any) =>
    request<any>("/api/auth/me", { method: "PUT", body: JSON.stringify(data) }),
};

// ── Agents ──

export const agents = {
  list: () => request<any[]>("/api/agents/"),

  create: (data: { name?: string; voice_language?: string; voice_gender?: string }) =>
    request<any>("/api/agents/", { method: "POST", body: JSON.stringify(data) }),

  get: (id: string) => request<any>(`/api/agents/${id}`),

  update: (id: string, data: any) =>
    request<any>(`/api/agents/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  launch: (id: string) =>
    request<any>(`/api/agents/${id}/launch`, { method: "POST" }),

  pause: (id: string) =>
    request<any>(`/api/agents/${id}/pause`, { method: "POST" }),

  stop: (id: string) =>
    request<any>(`/api/agents/${id}/stop`, { method: "POST" }),

  toggleGhostMode: (id: string) =>
    request<any>(`/api/agents/${id}/ghost-mode/toggle`, { method: "POST" }),

  delete: (id: string) =>
    request<any>(`/api/agents/${id}`, { method: "DELETE" }),

  integrationStatus: (id: string) =>
    request<any>(`/api/agents/${id}/integrations/status`),

  connectIntegration: (id: string, appName: string) =>
    request<any>(`/api/agents/${id}/integrations/connect/${appName}`, { method: "POST" }),
};

// ── Dashboard ──

export const dashboard = {
  stats: () => request<any>("/api/dashboard/stats"),

  decisions: (params?: { limit?: number; offset?: number; status_filter?: string; channel_filter?: string }) => {
    const q = new URLSearchParams();
    if (params?.limit) q.set("limit", String(params.limit));
    if (params?.offset) q.set("offset", String(params.offset));
    if (params?.status_filter) q.set("status_filter", params.status_filter);
    if (params?.channel_filter) q.set("channel_filter", params.channel_filter);
    return request<any>(`/api/dashboard/decisions?${q}`);
  },

  submitFeedback: (actionId: string, feedback: { type: string; edited_content?: string }) =>
    request<any>(`/api/dashboard/decisions/${actionId}/feedback`, { method: "POST", body: JSON.stringify(feedback) }),

  weeklyReport: () => request<any>("/api/dashboard/weekly-report"),
};

// ── Relationships ──

export const relationships = {
  graph: () => request<any>("/api/relationships/graph"),
  toneShifts: () => request<any>("/api/relationships/tone-shifts"),
  neglected: () => request<any>("/api/relationships/neglected"),
  keyContacts: () => request<any>("/api/relationships/key-contacts"),
  clusters: () => request<any>("/api/relationships/clusters"),
};

// ── Mesh ──

export const mesh = {
  status: () => request<any>("/api/mesh/status"),
  agents: () => request<any>("/api/mesh/agents"),
  requestMeeting: (data: { to_user_id: string; proposed_times: string[]; duration_minutes?: number; subject?: string }) =>
    request<any>("/api/mesh/meeting", { method: "POST", body: JSON.stringify(data) }),
  handoffTask: (data: { to_user_id: string; description: string }) =>
    request<any>("/api/mesh/handoff", { method: "POST", body: JSON.stringify(data) }),
};

// ── Marketplace ──

export const marketplace = {
  browse: (params?: { category?: string; search?: string; sort_by?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.category) q.set("category", params.category);
    if (params?.search) q.set("search", params.search);
    if (params?.sort_by) q.set("sort_by", params.sort_by);
    if (params?.limit) q.set("limit", String(params.limit));
    if (params?.offset) q.set("offset", String(params.offset));
    return request<any[]>(`/api/marketplace/listings?${q}`);
  },

  getListing: (id: string) => request<any>(`/api/marketplace/listings/${id}`),

  createListing: (data: { agent_id: string; title: string; description?: string; category?: string; capability_type?: string; price_per_use: number; tags?: string[] }) =>
    request<any>("/api/marketplace/listings", { method: "POST", body: JSON.stringify(data) }),

  updateListing: (id: string, data: any) =>
    request<any>(`/api/marketplace/listings/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  pauseListing: (id: string) =>
    request<any>(`/api/marketplace/listings/${id}/pause`, { method: "POST" }),

  activateListing: (id: string) =>
    request<any>(`/api/marketplace/listings/${id}/activate`, { method: "POST" }),

  purchase: (data: { listing_id: string; task_description?: string }) =>
    request<any>("/api/marketplace/purchase", { method: "POST", body: JSON.stringify(data) }),

  submitReview: (transactionId: string, data: { rating: number; review_text?: string }) =>
    request<any>(`/api/marketplace/transactions/${transactionId}/review`, { method: "POST", body: JSON.stringify(data) }),

  myListings: () => request<any[]>("/api/marketplace/my-listings"),

  myPurchases: () => request<any[]>("/api/marketplace/my-purchases"),

  sellerDashboard: () => request<any>("/api/marketplace/seller-dashboard"),
};

// ── Voice ──

export const voice = {
  token: (data: { mode: string; language: string }) =>
    request<{ token: string; url: string; room_name: string }>("/api/voice/token", { method: "POST", body: JSON.stringify(data) }),
};

export default { auth, agents, dashboard, relationships, mesh, marketplace, voice };
