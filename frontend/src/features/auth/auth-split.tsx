// Bố cục hai cột của Đăng nhập, Đăng ký (G-login, G-register): ảnh bên trái chỉ hiện từ 1024px.
import Image from "next/image";
import type { ReactNode } from "react";

import { cn } from "@/shared/lib/cn";
import { CheckIcon } from "@/shared/ui/icons";
import { Logo } from "@/shared/ui/logo";

type AuthSplitProps = {
  image: string;
  imagePosition: string;
  title: string;
  points: readonly string[];
  wideForm?: boolean;
  children: ReactNode;
};

export function AuthSplit({
  image,
  imagePosition,
  title,
  points,
  wideForm = false,
  children,
}: AuthSplitProps) {
  return (
    <div
      className={cn(
        "grid min-h-screen bg-ground",
        wideForm ? "lg:grid-cols-[5fr_7fr]" : "lg:grid-cols-2",
      )}
    >
      <aside className="relative hidden overflow-hidden bg-ink lg:block">
        <Image
          src={image}
          alt=""
          fill
          sizes="50vw"
          className="object-cover"
          style={{ objectPosition: imagePosition }}
        />
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-[linear-gradient(180deg,rgba(19,38,43,0.12)_0%,rgba(19,38,43,0.25)_45%,rgba(19,38,43,0.9)_100%)]"
        />
        <div className="absolute top-7 left-8 rounded-[10px] bg-white/92 py-1.5 pr-3 pl-1.5">
          <Logo />
        </div>
        <div className="absolute right-10 bottom-11 left-10 flex flex-col gap-3.5 text-white">
          <p className="text-[28px] leading-9 font-bold tracking-[-0.01em]">{title}</p>
          <ul className="flex flex-col gap-1.5 text-[15px] leading-[22px] text-[#e3ecee]">
            {points.map((point) => (
              <li key={point} className="flex items-center gap-2">
                <CheckIcon size={16} strokeWidth={2.6} className="shrink-0 text-[#7fd1c7]" />
                {point}
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <main className="flex flex-col justify-center px-4 py-8 sm:px-10 lg:px-12">
        <div
          className={cn(
            "mx-auto flex w-full flex-col gap-[18px]",
            wideForm ? "max-w-[560px]" : "max-w-[440px]",
          )}
        >
          <Logo className="mb-2 lg:hidden" />
          {children}
        </div>
      </main>
    </div>
  );
}
