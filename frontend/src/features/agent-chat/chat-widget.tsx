"use client";

// Khung chat của trợ lý, gắn ở layout gốc nên có trên mọi trang và giữ hội thoại khi chuyển trang
// (FR-AGT-01, docs mục 9.5). Chỉ bệnh nhân đã đăng nhập dùng; khách thấy nút dẫn tới đăng nhập.
import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { useChatPanel } from "@/shared/agent/chat-panel-store";
import { useAuthStore } from "@/shared/auth/auth-store";
import { TEXT } from "@/shared/texts";
import { ChatIcon } from "@/shared/ui/icons";

import { ChatPanel } from "./chat-panel";
import { useAgentChat } from "./use-agent-chat";

export function ChatWidget() {
  const user = useAuthStore((state) => state.user);
  const patient = user?.role === "PATIENT";
  const open = useChatPanel((state) => state.open);
  const openChat = useChatPanel((state) => state.openChat);
  const closeChat = useChatPanel((state) => state.closeChat);
  const chat = useAgentChat(open && patient);
  const pathname = usePathname();

  useEffect(() => {
    // Khách bấm "Hỏi trợ lý" → đăng nhập → quay lại trang cũ với ?chat=1: mở khung chat luôn.
    // Chạy lại khi đổi trang: đăng nhập xong mới chuyển từ /login sang trang có ?chat=1.
    if (!patient || !pathname) return;
    const url = new URL(window.location.href);
    if (url.searchParams.get("chat") !== "1") return;
    url.searchParams.delete("chat");
    window.history.replaceState(window.history.state, "", url);
    openChat();
  }, [patient, pathname, openChat]);

  useEffect(() => {
    // Máy tính: chừa chỗ cho panel để trang phía sau vẫn đọc và bấm được (globals.css).
    const root = document.documentElement;
    root.toggleAttribute("data-chat-open", open && patient);
    return () => root.removeAttribute("data-chat-open");
  }, [open, patient]);

  if (!patient) return null;
  if (open) {
    const firstName = user.full_name.trim().split(/\s+/).at(-1) ?? user.full_name;
    return <ChatPanel chat={chat} firstName={firstName} onClose={closeChat} />;
  }
  return (
    <button
      type="button"
      onClick={openChat}
      className="fixed right-6 bottom-6 z-40 hidden h-[52px] items-center gap-2.5 rounded-full bg-ink pr-5 pl-4 font-semibold text-white shadow-[0_8px_24px_rgba(19,38,43,0.24)] hover:bg-[#1d3a40] md:inline-flex"
    >
      <ChatIcon size={22} />
      {TEXT.agent.open}
    </button>
  );
}
