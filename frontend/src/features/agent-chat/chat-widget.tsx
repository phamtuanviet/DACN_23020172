"use client";

import { useAuthStore } from "@/shared/auth/auth-store";

// Khung chat nổi trên mọi trang, chỉ hiện với bệnh nhân đã đăng nhập (FR-AGT-01).
// Cần làm: useAgentChat (SSE qua @microsoft/fetch-event-source), MessageList, ProposalCard.
export function ChatWidget() {
  const role = useAuthStore((state) => state.user?.role);
  if (role !== "PATIENT") return null;
  return null;
}
