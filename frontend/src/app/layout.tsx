import type { Metadata } from "next";
import { connection } from "next/server";
import type { ReactNode } from "react";

import { ChatWidget } from "@/features/agent-chat";

import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: { default: "Đặt lịch khám bệnh", template: "%s · Đặt lịch khám bệnh" },
  description: "Đặt, đổi, hủy lịch khám trực tuyến hoặc qua trợ lý AI.",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  // CSP dùng nonce mới cho mỗi request (src/proxy.ts), nên mọi trang phải render động.
  await connection();
  return (
    <html lang="vi">
      <body className="min-h-screen bg-white text-gray-900 antialiased">
        <Providers>
          {children}
          <ChatWidget />
        </Providers>
      </body>
    </html>
  );
}
