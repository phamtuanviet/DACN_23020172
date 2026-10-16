// Trạng thái đăng nhập phía trình duyệt. Access token CHỈ nằm trong bộ nhớ,
// không ghi vào localStorage (docs mục 4.6); refresh token nằm trong cookie HttpOnly.
import { create } from "zustand";

import type { components } from "@/shared/api/schema";

export type Role = components["schemas"]["UserRole"];
export type SessionUser = components["schemas"]["MeResponse"];

// unknown: chưa hỏi backend (vừa mở trang) · authenticated · anonymous: chắc chắn chưa đăng nhập
export type SessionStatus = "unknown" | "authenticated" | "anonymous";

type AuthState = {
  status: SessionStatus;
  accessToken: string | null;
  user: SessionUser | null;
  setSession: (accessToken: string, user: SessionUser) => void;
  setUser: (user: SessionUser) => void;
  clear: () => void;
};

export const useAuthStore = create<AuthState>()((set) => ({
  status: "unknown",
  accessToken: null,
  user: null,
  setSession: (accessToken, user) => set({ status: "authenticated", accessToken, user }),
  setUser: (user) => set({ user }),
  clear: () => set({ status: "anonymous", accessToken: null, user: null }),
}));
