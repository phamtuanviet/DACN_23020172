// Ô tìm dịch vụ, bác sĩ: form GET tới /services nên chạy được cả khi chưa tải JavaScript;
// next/form chuyển trang phía client khi JavaScript đã sẵn sàng.
import Form from "next/form";
import Link from "next/link";

import { cn } from "@/shared/lib/cn";
import { TEXT } from "@/shared/texts";
import { buttonClass } from "@/shared/ui/button";
import { CloseIcon, SearchIcon } from "@/shared/ui/icons";

export function SearchForm({
  defaultValue,
  placeholder,
  hidden = {},
  clearHref,
  className,
}: {
  defaultValue?: string;
  placeholder: string;
  /** Giữ bộ lọc đang chọn khi tìm (ví dụ chuyên khoa, tab). */
  hidden?: Record<string, string | undefined>;
  /** Có từ khóa thì hiện nút xóa, dẫn về trang không có từ khóa và viền ô nổi bật. */
  clearHref?: string;
  className?: string;
}) {
  return (
    <Form
      action="/services"
      role="search"
      className={cn(
        "flex gap-2 rounded-card bg-surface p-1.5 shadow-[0_8px_24px_rgba(19,38,43,0.06)]",
        clearHref
          ? "border-[1.5px] border-primary ring-3 ring-primary/12"
          : "border border-line-strong",
        className,
      )}
    >
      {Object.entries(hidden).map(([name, value]) =>
        value ? <input key={name} type="hidden" name={name} value={value} /> : null,
      )}
      <label className="flex min-w-0 flex-1 items-center gap-2 pl-2.5">
        <SearchIcon size={20} className="shrink-0 text-muted" />
        <span className="sr-only">{TEXT.catalog.searchLabel}</span>
        <input
          type="search"
          name="q"
          defaultValue={defaultValue}
          placeholder={placeholder}
          maxLength={100}
          className="h-11 min-w-0 flex-1 bg-transparent outline-none placeholder:text-muted [&::-webkit-search-cancel-button]:hidden"
        />
      </label>
      {clearHref ? (
        <Link
          href={clearHref}
          aria-label={TEXT.catalog.clearSearch}
          className="flex size-11 shrink-0 items-center justify-center rounded-control text-muted hover:bg-ground"
        >
          <CloseIcon size={18} />
        </Link>
      ) : null}
      <button type="submit" className={buttonClass({ className: "px-5" })}>
        {TEXT.home.search}
      </button>
    </Form>
  );
}
