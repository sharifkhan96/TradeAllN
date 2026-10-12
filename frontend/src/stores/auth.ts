import { create } from "zustand";
import type { User } from "@/lib/types";

type AuthState = {
  access: string | null;
  user: User | null;
  ready: boolean;
  setSession: (access: string, user: User) => void;
  setUser: (user: User) => void;
  clear: () => void;
  setReady: () => void;
};

export const useAuth = create<AuthState>((set) => ({
  access: null,
  user: null,
  ready: false,
  setSession: (access, user) => set({ access, user }),
  setUser: (user) => set({ user }),
  clear: () => set({ access: null, user: null }),
  setReady: () => set({ ready: true }),
}));
