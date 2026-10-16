"use client";

import { useEffect } from "react";

import { bootstrapSession } from "./session";

// Gắn một lần ở layout gốc: mở trang là biết ngay người dùng còn phiên đăng nhập hay không.
export function SessionBootstrap() {
  useEffect(() => {
    bootstrapSession();
  }, []);
  return null;
}
