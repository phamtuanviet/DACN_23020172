"use client";

// Số việc trong hàng chờ của quản trị (FR-ADM-04): lịch cần xử lý + yêu cầu gặp nhân viên đang mở.
// Thanh bên của khu vực quản trị và tab Hàng chờ cùng dùng; tự tải lại mỗi 60 giây (docs mục 9.4).
import { useQuery } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import { toApiError } from "@/shared/api/errors";

const REFRESH_MS = 60_000;

export function useQueueCount(enabled = true) {
  return useQuery({
    queryKey: ["admin", "queue-count"],
    enabled,
    refetchInterval: REFRESH_MS,
    queryFn: async (): Promise<number> => {
      const [flagged, support] = await Promise.all([
        api.GET("/api/v1/admin/appointments", {
          params: { query: { needs_attention: true, page_size: 1 } },
        }),
        api.GET("/api/v1/admin/support-requests", { params: { query: { status: "OPEN" } } }),
      ]);
      if (!flagged.data) throw toApiError(flagged.error);
      if (!support.data) throw toApiError(support.error);
      return flagged.data.total + support.data.length;
    },
  });
}
