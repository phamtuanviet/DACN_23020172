"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { SessionBootstrap } from "@/shared/auth/session-bootstrap";
import { Toaster } from "@/shared/ui/toast";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } } }),
  );
  return (
    <QueryClientProvider client={queryClient}>
      <SessionBootstrap />
      {children}
      <Toaster />
    </QueryClientProvider>
  );
}
