import type { Metadata, Viewport } from "next";
import { Be_Vietnam_Pro } from "next/font/google";
import { connection } from "next/server";
import type { ReactNode } from "react";

import { ChatWidget } from "@/features/agent-chat";

import "./globals.css";
import { Providers } from "./providers";

// Font tự host lúc build (next/font): trình duyệt không gọi Google, hợp CSP font-src 'self'.
const beVietnamPro = Be_Vietnam_Pro({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-be-vietnam-pro",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "Đặt lịch khám bệnh", template: "%s · Đặt lịch khám bệnh" },
  description: "Đặt, đổi, hủy lịch khám trực tuyến hoặc qua trợ lý AI.",
};

export const viewport: Viewport = { themeColor: "#0d6b66" };

export default async function RootLayout({ children }: { children: ReactNode }) {
  // CSP dùng nonce mới cho mỗi request (src/proxy.ts), nên mọi trang phải render động.
  await connection();
  return (
    <html lang="vi" className={beVietnamPro.variable}>
      <body className="min-h-screen">
        <Providers>
          {children}
          <ChatWidget />
        </Providers>
      </body>
    </html>
  );
}
