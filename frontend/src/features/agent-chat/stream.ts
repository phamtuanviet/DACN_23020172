// Gửi một lượt chat và đọc luồng SSE (docs mục 8.4, 9.5). Dùng fetch-event-source vì EventSource của
// trình duyệt chỉ hỗ trợ GET và không gửi được header Authorization.
import { EventStreamContentType, fetchEventSource } from "@microsoft/fetch-event-source";

import { toApiError, type ApiError } from "@/shared/api/errors";
import { useAuthStore } from "@/shared/auth/auth-store";
import { refreshSession } from "@/shared/auth/session";

import type { ChatRequest } from "./reducer";

export class ChatHttpError extends Error {
  constructor(
    readonly error: ApiError,
    readonly status: number,
  ) {
    super(error.message);
  }
}

class Unauthorized extends Error {}

/**
 * Lỗi trước khi mở luồng (hết lượt 429, tạm ngưng 503, hội thoại không còn 404…) ném ChatHttpError.
 * Access token hết hạn thì refresh một lần rồi gửi lại: backend chưa lưu tin nhắn nào khi trả 401.
 * Không tự kết nối lại khi luồng đứt, vì gửi lại sẽ thành một tin nhắn mới.
 */
export async function streamChat(
  body: ChatRequest,
  onEvent: (name: string, data: unknown) => void,
  signal: AbortSignal,
): Promise<void> {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const token = useAuthStore.getState().accessToken;
    try {
      await fetchEventSource("/api/v1/agent/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: EventStreamContentType,
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
        signal,
        openWhenHidden: true, // mặc định thư viện đóng rồi mở lại luồng khi đổi tab: sẽ gửi lại tin
        async onopen(response) {
          const type = response.headers.get("content-type") ?? "";
          if (response.ok && type.startsWith(EventStreamContentType)) return;
          if (response.status === 401 && attempt === 0) throw new Unauthorized();
          const json: unknown = await response.json().catch(() => null);
          throw new ChatHttpError(toApiError(json), response.status);
        },
        onmessage(message) {
          if (!message.event) return;
          onEvent(message.event, message.data ? JSON.parse(message.data) : null);
        },
        onerror(error) {
          throw error;
        },
      });
      return;
    } catch (error) {
      if (!(error instanceof Unauthorized)) throw error;
      if (!(await refreshSession())) {
        throw new ChatHttpError(toApiError({ code: "UNAUTHENTICATED", message: "" }), 401);
      }
    }
  }
}
