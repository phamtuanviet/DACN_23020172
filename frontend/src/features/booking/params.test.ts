import { describe, expect, it } from "vitest";

import { currentStep, parseBookingParams } from "./params";

const parse = (query: string) => parseBookingParams(new URLSearchParams(query));

describe("parseBookingParams", () => {
  it("đọc đủ lựa chọn của wizard", () => {
    expect(parse("specialty=2&service=5&doctor=7&date=2026-10-17")).toEqual({
      q: undefined,
      specialty: 2,
      service: 5,
      doctor: 7,
      date: "2026-10-17",
      start: undefined,
    });
    expect(parse("service=5&doctor=any").doctor).toBe("any");
  });

  it("bỏ qua giá trị sai dạng", () => {
    expect(parse("service=abc&doctor=-1&date=2026-02-30&start=xyz")).toEqual({
      q: undefined,
      specialty: undefined,
      service: undefined,
      doctor: undefined,
      date: undefined,
      start: undefined,
    });
  });
});

describe("currentStep", () => {
  it("suy ra bước từ lựa chọn đã có", () => {
    expect(currentStep(parse(""))).toBe(0);
    expect(currentStep(parse("specialty=2"))).toBe(0);
    expect(currentStep(parse("service=5"))).toBe(1);
    expect(currentStep(parse("service=5&doctor=any"))).toBe(2);
  });
});
