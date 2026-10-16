// Thước đo độ mạnh mật khẩu 3 nấc dưới ô mật khẩu (G-register). Có chữ đi kèm, không chỉ dựa vào màu.
import { cn } from "@/shared/lib/cn";
import { TEXT } from "@/shared/texts";

import { passwordStrength } from "./validation";

const LEVEL = { weak: 1, medium: 2, strong: 3 } as const;
const BAR = { weak: "bg-amber", medium: "bg-primary", strong: "bg-success" } as const;
const LABEL = {
  weak: "text-amber-ink",
  medium: "text-primary-ink",
  strong: "text-success",
} as const;

// showHint=false khi ô đang báo lỗi, để gợi ý không lặp lại dòng lỗi ngay bên dưới.
export function PasswordMeter({
  password,
  showHint = true,
}: {
  password: string;
  showHint?: boolean;
}) {
  if (!password) {
    return <span className="text-[13px] leading-[18px] text-muted">{TEXT.auth.strengthHint}</span>;
  }
  const strength = passwordStrength(password);
  return (
    <span className="flex flex-col gap-1.5">
      <span aria-hidden="true" className="grid grid-cols-3 gap-1">
        {[1, 2, 3].map((step) => (
          <span
            key={step}
            className={cn(
              "h-1 rounded-full",
              step <= LEVEL[strength] ? BAR[strength] : "bg-divider",
            )}
          />
        ))}
      </span>
      <span className={cn("text-[13px] leading-[18px]", LABEL[strength])}>
        <b>{TEXT.auth.strength[strength]}</b>
        {strength === "weak" && showHint ? ` · ${TEXT.auth.strengthHint}` : null}
      </span>
    </span>
  );
}
