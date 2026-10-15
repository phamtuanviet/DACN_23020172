import { describe, expect, it } from "vitest";

import { formatDateTime } from "./datetime";

describe("formatDateTime", () => {
  it("hiển thị theo giờ Việt Nam dù đầu vào là UTC", () => {
    expect(formatDateTime("2026-10-17T01:00:00Z")).toMatch(/17\/10\/2026 08:00$/);
  });
});
