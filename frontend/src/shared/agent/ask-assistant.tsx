"use client";

// Nút "Hỏi trợ lý": bệnh nhân thì mở khung chat; khách thì đăng nhập rồi quay lại với khung chat
// đang mở; bác sĩ, quản trị không dùng trợ lý nên không hiện (FR-AGT-01).
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuthStore } from "@/shared/auth/auth-store";
import { TEXT } from "@/shared/texts";
import { buttonClass, type ButtonVariant } from "@/shared/ui/button";
import { ChatIcon } from "@/shared/ui/icons";

import { loginHrefForChat, useChatPanel } from "./chat-panel-store";

export function AskAssistantButton({
  variant = "outline",
  className,
}: {
  variant?: ButtonVariant;
  className?: string;
}) {
  const pathname = usePathname();
  const status = useAuthStore((state) => state.status);
  const role = useAuthStore((state) => state.user?.role);
  const openChat = useChatPanel((state) => state.openChat);
  const look = buttonClass({ variant, className });

  if (role === "PATIENT") {
    return (
      <button type="button" onClick={openChat} className={look}>
        <ChatIcon size={18} />
        {TEXT.agent.open}
      </button>
    );
  }
  if (status === "authenticated") return null;
  return (
    <Link href={loginHrefForChat(pathname)} className={look}>
      <ChatIcon size={18} />
      {TEXT.agent.open}
    </Link>
  );
}
