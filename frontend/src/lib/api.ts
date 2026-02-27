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

// ── Commitments ──

export const commitments = {
  list: (params?: { status?: string; contact?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.contact) q.set("contact", params.contact);
    return request<any[]>(`/api/commitments/?${q}`);
  },
  stats: () => request<any>("/api/commitments/stats"),
  fulfill: (id: string) => request<any>(`/api/commitments/${id}/fulfill`, { method: "POST" }),
  cancel: (id: string) => request<any>(`/api/commitments/${id}/cancel`, { method: "POST" }),
  snooze: (id: string) => request<any>(`/api/commitments/${id}/snooze`, { method: "POST" }),
  correlation: (contact: string) => request<any>(`/api/commitments/correlation/${contact}`),
};

// ── Delegation ──

export const delegation = {
  propose: (data: { task: string; to_user_id?: string }) =>
    request<any>("/api/delegation/propose", { method: "POST", body: JSON.stringify(data) }),
  candidates: (task: string) => request<any[]>(`/api/delegation/candidates?task=${encodeURIComponent(task)}`),
  list: () => request<any>("/api/delegation/"),
  accept: (id: string) => request<any>(`/api/delegation/${id}/accept`, { method: "POST" }),
  reject: (id: string, note?: string) => request<any>(`/api/delegation/${id}/reject`, { method: "POST", body: JSON.stringify({ note: note || "" }) }),
  complete: (id: string) => request<any>(`/api/delegation/${id}/complete`, { method: "POST" }),
  stats: () => request<any>("/api/delegation/stats"),
};

// ── Burnout / Wellness ──

export const burnout = {
  current: () => request<any>("/api/burnout/current"),
  trend: () => request<any[]>("/api/burnout/trend"),
  interventions: () => request<any[]>("/api/burnout/interventions"),
  applyIntervention: (id: string) => request<any>(`/api/burnout/interventions/${id}/apply`, { method: "POST" }),
  coldContacts: () => request<any[]>("/api/burnout/cold-contacts"),
  productivity: () => request<any>("/api/burnout/productivity"),
};

// ── Decision Replay ──

export const replay = {
  list: () => request<any[]>("/api/replay/"),
  detail: (id: string) => request<any>(`/api/replay/${id}`),
  generate: (actionId: string) => request<any>(`/api/replay/generate/${actionId}`, { method: "POST" }),
  weekly: () => request<any[]>("/api/replay/weekly"),
};

// ── Flow Guardian ──

export const flow = {
  status: () => request<any>("/api/flow/status"),
  signal: (data: { signal_type: string; metadata?: object }) =>
    request<any>("/api/flow/signal", { method: "POST", body: JSON.stringify(data) }),
  activate: () => request<any>("/api/flow/activate", { method: "POST" }),
  end: () => request<any>("/api/flow/end", { method: "POST" }),
  debrief: (sessionId: string) => request<any>(`/api/flow/debrief/${sessionId}`),
  history: () => request<any[]>("/api/flow/history"),
  stats: () => request<any>("/api/flow/stats"),
};

export default { auth, agents, dashboard, relationships, mesh, marketplace, voice, commitments, delegation, burnout, replay, flow };
