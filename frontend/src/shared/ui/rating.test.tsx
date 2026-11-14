import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { RatingSummary, Stars } from "./rating";

afterEach(cleanup);

describe("RatingSummary", () => {
  it("đủ lượt thì hiện điểm kiểu Việt Nam và số lượt, đọc được bằng trình đọc màn hình", () => {
    render(<RatingSummary average={4.8} count={36} />);
    expect(screen.getByText("Điểm đánh giá 4,8 trên 5, 36 lượt")).toBeTruthy();
    expect(screen.getByText("trên 5 · 36 đánh giá")).toBeTruthy();
  });

  it("dạng gọn cho thẻ bác sĩ", () => {
    render(<RatingSummary average={4} count={3} compact />);
    expect(screen.getByText("4,0")).toBeTruthy();
    expect(screen.getByText("(3)")).toBeTruthy();
  });

  it("chưa đủ lượt để có điểm thì chỉ hiện số lượt, không ghi là chưa có đánh giá", () => {
    render(<RatingSummary average={null} count={2} />);
    expect(screen.getByText("2 đánh giá, chưa đủ để hiện điểm")).toBeTruthy();
    expect(screen.queryByText("Chưa có đánh giá")).toBeNull();
  });

  it("chưa có lượt nào", () => {
    render(<RatingSummary average={null} count={0} compact />);
    expect(screen.getByText("Chưa có đánh giá")).toBeTruthy();
  });
});

describe("Stars", () => {
  it("năm ngôi sao, nhãn đọc số sao đã chấm", () => {
    render(<Stars value={4} />);
    expect(screen.getByRole("img", { name: "4 trên 5 sao" })).toBeTruthy();
  });
});
