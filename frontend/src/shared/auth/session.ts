// Phiên đăng nhập: lấy access token bằng cookie refresh, đăng xuất (docs mục 9.4, 10.1).
// Gọi fetch trực tiếp, không qua shared/api/client.ts, để không vòng lặp khi client gặp 401.
import type { components } from "@/shared/api/schema";

import { useAuthStore } from "./auth-store";

type TokenResponse = components["schemas"]["TokenResponse"];

let inflight: Promise<TokenResponse | null> | null = null;

/** Đổi cookie refresh lấy access token mới. Các lời gọi đồng thời dùng chung một request. */
export function refreshSession(): Promise<TokenResponse | null> {
  inflight ??= (async () => {
    try {
      const response = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        credentials: "same-origin",
      });
      if (!response.ok) {
        useAuthStore.getState().clear();
        return null;
      }
      const session = (await response.json()) as TokenResponse;
      useAuthStore.getState().setSession(session.access_token, session.user);
      return session;
    } catch {
      useAuthStore.getState().clear();
      return null;
    }
  })().finally(() => {
    inflight = null;
  });
  return inflight;
}

/** Lần đầu mở ứng dụng: hỏi backend xem cookie refresh còn hiệu lực không. */
export function bootstrapSession(): void {
  if (useAuthStore.getState().status === "unknown") void refreshSession();
}

export async function logout(): Promise<void> {
  try {
    await fetch("/api/v1/auth/logout", { method: "POST", credentials: "same-origin" });
  } finally {
    useAuthStore.getState().clear();
  }
}
