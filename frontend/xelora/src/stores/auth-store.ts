'use client';

import { create } from 'zustand';
import type { User } from '@/types';
import { getSession, logout as logoutService } from '@/services/auth';

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  initialize: () => Promise<void>;
  setUser: (user: User) => void;
  logout: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: true,
  isAuthenticated: false,

  initialize: async () => {
    const session = await getSession();
    if (session) {
      set({ user: session.user, isAuthenticated: true, isLoading: false });
    } else {
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  setUser: (user: User) => {
    set({ user, isAuthenticated: true });
  },

  logout: async () => {
    await logoutService();
    set({ user: null, isAuthenticated: false });
  },
}));
