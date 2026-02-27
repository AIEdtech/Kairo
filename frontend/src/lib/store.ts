/**
 * Auth store — Zustand state management for user authentication
 */
import { create } from "zustand";
import { auth as authApi } from "./api";

interface User {
  id: string;
  email: string;
  username: string;
  full_name: string;
  avatar_url: string;
  preferred_language: string;
  timezone: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  error: string | null;

  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; username: string; password: string; full_name?: string }) => Promise<void>;
  logout: () => void;
  loadUser: () => Promise<void>;
  clearError: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  token: typeof window !== "undefined" ? localStorage.getItem("kairo_token") : null,
  isLoading: false,
  error: null,

  login: async (email, password) => {
    set({ isLoading: true, error: null });
    try {
      const res = await authApi.login({ email, password });
      localStorage.setItem("kairo_token", res.access_token);
      set({ user: res.user, token: res.access_token, isLoading: false });
    } catch (err: any) {
      set({ error: err.message, isLoading: false });
    }
  },

  register: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const res = await authApi.register(data);
      localStorage.setItem("kairo_token", res.access_token);
      set({ user: res.user, token: res.access_token, isLoading: false });
    } catch (err: any) {
      set({ error: err.message, isLoading: false });
    }
  },

  logout: () => {
    localStorage.removeItem("kairo_token");
    set({ user: null, token: null });
  },

  loadUser: async () => {
    const token = localStorage.getItem("kairo_token");
    if (!token) return;
    set({ isLoading: true });
    try {
      const user = await authApi.me();
      set({ user, token, isLoading: false });
    } catch {
      localStorage.removeItem("kairo_token");
      set({ user: null, token: null, isLoading: false });
    }
  },

  clearError: () => set({ error: null }),
}));
