"use client";

// Lỗi không lường trước khi render (ví dụ backend không phản hồi lúc tải danh mục): chỉ hiện
// thông báo chung, không lộ chi tiết kỹ thuật (SRS mục 7.1).
import Link from "next/link";

import { TEXT } from "@/shared/texts";
import { Button, buttonClass } from "@/shared/ui/button";
import { AlertIcon } from "@/shared/ui/icons";

export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto flex max-w-xl flex-col items-center gap-3 px-4 py-16 text-center">
      <span
        aria-hidden="true"
        className="flex size-12 items-center justify-center rounded-full bg-danger-soft text-danger"
      >
        <AlertIcon size={24} />
      </span>
      <h1 className="text-2xl font-semibold">Hệ thống đang gặp sự cố</h1>
      <p className="text-muted">{TEXT.common.genericError}</p>
      <div className="mt-2 flex gap-3">
        <Button onClick={reset}>{TEXT.common.retry}</Button>
        <Link href="/" className={buttonClass({ variant: "secondary" })}>
          {TEXT.common.backHome}
        </Link>
      </div>
    </main>
  );
}
