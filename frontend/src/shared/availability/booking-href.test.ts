import { describe, expect, it } from "vitest";

import { bookingHref } from "./booking-href";

describe("bookingHref", () => {
  it("giữ lựa chọn của wizard trên URL", () => {
    expect(bookingHref({})).toBe("/booking");
    expect(bookingHref({ specialty: 2, service: 5 })).toBe("/booking?specialty=2&service=5");
    expect(
      bookingHref({
        service: 5,
        doctor: "any",
        date: "2026-10-17",
        start: "2026-10-17T08:00:00+07:00",
      }),
    ).toBe("/booking?service=5&doctor=any&date=2026-10-17&start=2026-10-17T08%3A00%3A00%2B07%3A00");
  });
});
