// Trạng thái đăng nhập phía trình duyệt. Access token CHỈ nằm trong bộ nhớ,
// không ghi vào localStorage (docs mục 4.6); refresh token nằm trong cookie HttpOnly.
import { create } from "zustand";

export type Role = "PATIENT" | "DOCTOR" | "ADMIN";
export type SessionUser = { id: number; fullName: string; role: Role };

type AuthState = {
  accessToken: string | null;
  user: SessionUser | null;
  setSession: (accessToken: string, user: SessionUser) => void;
  clear: () => void;
};

export const useAuthStore = create<AuthState>()((set) => ({
  accessToken: null,
  user: null,
  setSession: (accessToken, user) => set({ accessToken, user }),
  clear: () => set({ accessToken: null, user: null }),
}));
