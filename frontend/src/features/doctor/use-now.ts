"use client";

import { useEffect, useState } from "react";

/** Giờ hiện tại, cập nhật mỗi phút: vạch "Bây giờ" và nút Vắng mặt bật đúng lúc tới giờ khám. */
export function useNow(): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(timer);
  }, []);
  return now;
}
