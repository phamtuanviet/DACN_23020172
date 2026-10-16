// Chỉ dùng trong client component. Hộp thoại dựa trên <dialog> gốc của trình duyệt: tự giữ focus bên trong, Esc để đóng, có nền mờ.
import { useEffect, useId, useRef, type ReactNode } from "react";

import { CloseIcon } from "./icons";

type DialogProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
};

export function Dialog({ open, onClose, title, description, children, footer }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === ref.current) onClose(); // bấm ra nền mờ
      }}
      className="m-auto w-[calc(100%-32px)] max-w-lg rounded-card bg-surface p-0 text-ink shadow-xl backdrop:bg-ink/50"
    >
      <div className="flex flex-col gap-4 p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h2 id={titleId} className="text-lg font-semibold">
              {title}
            </h2>
            {description ? <p className="text-sm text-muted">{description}</p> : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng"
            className="-m-2 rounded-control p-2 text-muted hover:bg-ground"
          >
            <CloseIcon size={20} />
          </button>
        </div>
        {children}
        {footer ? <div className="flex flex-wrap justify-end gap-2 pt-2">{footer}</div> : null}
      </div>
    </dialog>
  );
}
