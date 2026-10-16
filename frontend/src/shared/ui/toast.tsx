"use client";

// Thông báo kết quả thao tác (docs mục 9.6): góc dưới trên máy tính, trên thanh tab ở điện thoại.
import { create } from "zustand";

import { cn } from "@/shared/lib/cn";

import { AlertIcon, CheckIcon, CloseIcon } from "./icons";

type ToastTone = "success" | "error";
type ToastItem = { id: number; tone: ToastTone; message: string };

type ToastState = {
  items: ToastItem[];
  push: (tone: ToastTone, message: string) => void;
  dismiss: (id: number) => void;
};

let nextId = 1;

const useToastStore = create<ToastState>()((set, get) => ({
  items: [],
  push: (tone, message) => {
    const id = nextId++;
    set({ items: [...get().items, { id, tone, message }] });
    setTimeout(() => get().dismiss(id), 4500);
  },
  dismiss: (id) => set({ items: get().items.filter((item) => item.id !== id) }),
}));

export const toast = {
  success: (message: string) => useToastStore.getState().push("success", message),
  error: (message: string) => useToastStore.getState().push("error", message),
};

export function Toaster() {
  const items = useToastStore((state) => state.items);
  const dismiss = useToastStore((state) => state.dismiss);
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-4 bottom-20 z-50 flex flex-col items-center gap-2 md:inset-x-auto md:right-6 md:bottom-6 md:items-end"
    >
      {items.map((item) => (
        <div
          key={item.id}
          role={item.tone === "error" ? "alert" : "status"}
          className={cn(
            "pointer-events-auto flex w-full max-w-sm items-start gap-2.5 rounded-card px-4 py-3 text-sm text-white shadow-lg",
            item.tone === "error" ? "bg-danger" : "bg-ink",
          )}
        >
          {item.tone === "error" ? (
            <AlertIcon size={18} className="mt-px shrink-0" />
          ) : (
            <CheckIcon size={18} className="mt-px shrink-0" />
          )}
          <span className="flex-1">{item.message}</span>
          <button
            type="button"
            onClick={() => dismiss(item.id)}
            aria-label="Đóng thông báo"
            className="-m-1 p-1 opacity-80 hover:opacity-100"
          >
            <CloseIcon size={16} />
          </button>
        </div>
      ))}
    </div>
  );
}
