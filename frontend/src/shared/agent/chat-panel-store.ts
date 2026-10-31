// Khung chat của trợ lý đang mở hay đóng. Nằm ở shared để nút "Hỏi trợ lý" ở trang chủ, danh mục,
// wizard và thanh tab mở được khung chat mà không import feature agent-chat (docs mục 9.2, 9.5).
import { create } from "zustand";

type ChatPanelState = {
  open: boolean;
  openChat: () => void;
  closeChat: () => void;
  toggleChat: () => void;
};

export const useChatPanel = create<ChatPanelState>()((set, get) => ({
  open: false,
  openChat: () => set({ open: true }),
  closeChat: () => set({ open: false }),
  toggleChat: () => set({ open: !get().open }),
}));

/** Đăng nhập xong thì quay lại trang đang xem và mở luôn khung chat (?chat=1). */
export function loginHrefForChat(pathname: string): string {
  return `/login?next=${encodeURIComponent(`${pathname}?chat=1`)}`;
}
