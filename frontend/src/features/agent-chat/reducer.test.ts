import { describe, expect, it } from "vitest";

import { plainText, shortDoctor } from "./chat-panel";
import { formatCountdown, msLeft } from "./countdown";
import {
  chatReducer,
  initialChat,
  type ChatAction,
  type ChatState,
  type Conversation,
  type ProposalOut,
} from "./reducer";

const slot = {
  doctor_id: 7,
  doctor_name: "ThS. BS. Trần Minh",
  start_at: "2026-10-17T08:00:00+07:00",
  end_at: "2026-10-17T08:20:00+07:00",
  label: "Thứ Bảy 17/10, 08:00–08:20",
};

function proposal(id: string, status: ProposalOut["status"] = "PENDING"): ProposalOut {
  return {
    id,
    type: "BOOK",
    status,
    expires_at: "2026-10-10T09:10:00+07:00",
    display: {
      service: "Khám da liễu tổng quát",
      doctor: "ThS. BS. Trần Minh",
      when: "Thứ Bảy, 17/10/2026 · 08:00–08:20",
    },
    appointment_id: null,
  };
}

function run(actions: ChatAction[], from: ChatState = initialChat): ChatState {
  return actions.reduce(chatReducer, from);
}

const event = (name: string, data: unknown): ChatAction => ({ type: "event", name, data });

describe("chatReducer với sự kiện SSE", () => {
  it("dựng một lượt: trạng thái tool, nút khung giờ, chữ trả lời, số tin còn lại", () => {
    const state = run([
      { type: "send", text: "Tôi muốn khám da liễu sáng thứ Bảy tuần sau" },
      event("meta", { conversation_id: "c-1", user_message_id: 1 }),
      event("tool", { name: "search_services", status: "start", label: "Đang tìm dịch vụ…" }),
      event("tool", {
        name: "search_services",
        status: "end",
        label: "Đã tìm dịch vụ: Khám da liễu tổng quát",
        ok: true,
      }),
      event("tool", {
        name: "find_available_slots",
        status: "start",
        label: "Đang tìm khung giờ trống…",
      }),
      event("tool", {
        name: "find_available_slots",
        status: "end",
        label: "Đã tìm khung trống sáng Thứ Bảy 17/10",
        ok: true,
      }),
      event("slots", { slots: [slot] }),
      event("token", { text: "Sáng Thứ Bảy " }),
      event("token", { text: "còn 5 khung." }),
      event("done", { assistant_message_id: 4, remaining_quota: 46 }),
    ]);
    expect(state.conversationId).toBe("c-1");
    expect(state.streaming).toBe(false);
    expect(state.remaining).toBe(46);
    const [turn] = state.turns;
    expect(turn?.user).toBe("Tôi muốn khám da liễu sáng thứ Bảy tuần sau");
    expect(turn?.tools.map((t) => [t.label, t.done])).toEqual([
      ["Đã tìm dịch vụ: Khám da liễu tổng quát", true],
      ["Đã tìm khung trống sáng Thứ Bảy 17/10", true],
    ]);
    expect(turn?.texts).toEqual(["Sáng Thứ Bảy còn 5 khung."]);
    expect(turn?.slots).toEqual([slot]);
  });

  it("chữ trước và sau một lần gọi tool nằm ở hai bong bóng", () => {
    const state = run([
      { type: "send", text: "Hủy lịch thứ Hai" },
      event("token", { text: "Để mình xem lịch của bạn." }),
      event("tool", { name: "get_my_appointments", status: "start", label: "…" }),
      event("tool", {
        name: "get_my_appointments",
        status: "end",
        label: "Đã xem lịch hẹn của bạn",
        ok: true,
      }),
      event("token", { text: "Bạn có một lịch thứ Hai." }),
    ]);
    expect(state.turns[0]?.texts).toEqual([
      "Để mình xem lịch của bạn.",
      "Bạn có một lịch thứ Hai.",
    ]);
  });

  it("thẻ mới thay thẻ cũ đang chờ; xác nhận cập nhật đúng thẻ", () => {
    let state = run([
      { type: "send", text: "Đặt 8 giờ" },
      event("proposal", proposal("p-1")),
      { type: "send", text: "Thôi đổi sang 8 giờ 20" },
      event("proposal", proposal("p-2")),
    ]);
    expect(state.turns[0]?.proposals[0]?.status).toBe("EXPIRED");
    expect(state.turns[1]?.proposals[0]?.status).toBe("PENDING");
    state = chatReducer(state, {
      type: "proposal",
      proposal: { ...proposal("p-2", "CONFIRMED"), appointment_code: "LH-261010-7KQ2" },
    });
    expect(state.turns[1]?.proposals[0]?.appointment_code).toBe("LH-261010-7KQ2");
  });

  it("lượt ẩn sau đề xuất thất bại không hiện câu hỏi", () => {
    const state = run([
      { type: "send", text: null },
      event("token", { text: "Khung khác: 08:20." }),
    ]);
    expect(state.turns[0]?.user).toBeNull();
    expect(state.turns[0]?.texts).toEqual(["Khung khác: 08:20."]);
  });

  it("hết lượt hoặc tạm ngưng thì khóa ô nhập; lỗi khác hiện ngay trong lượt", () => {
    const quota = run([
      { type: "send", text: "Xin chào" },
      { type: "failed", error: { code: "AGENT_QUOTA_EXCEEDED", message: "Hết lượt" } },
    ]);
    expect(quota.blocked).toBe("quota");
    expect(quota.remaining).toBe(0);
    const timeout = run([
      { type: "send", text: "Xin chào" },
      event("error", { code: "AGENT_TIMEOUT", message: "Trợ lý phản hồi quá lâu." }),
      event("done", { assistant_message_id: null, remaining_quota: 30 }),
    ]);
    expect(timeout.blocked).toBeNull();
    expect(timeout.turns[0]?.error?.code).toBe("AGENT_TIMEOUT");
  });
});

describe("tải lại hội thoại", () => {
  it("mỗi tin của người dùng mở một lượt; tool mang theo khung giờ và thẻ", () => {
    const conversation: Conversation = {
      id: "c-1",
      remaining_quota: 47,
      items: [
        { id: 1, kind: "user", created_at: "", text: "Khám da liễu thứ Bảy", hidden: false },
        {
          id: 2,
          kind: "tool",
          created_at: "",
          hidden: false,
          tool: {
            name: "find_available_slots",
            status: "end",
            label: "Đã tìm khung trống",
            ok: true,
          },
          slots: [slot],
        },
        { id: 3, kind: "assistant", created_at: "", text: "Còn các khung sau.", hidden: false },
        { id: 4, kind: "user", created_at: "", text: "Đặt 8 giờ", hidden: false },
        {
          id: 5,
          kind: "tool",
          created_at: "",
          hidden: false,
          tool: {
            name: "propose_booking",
            status: "end",
            label: "Đã tạo đề xuất đặt lịch",
            ok: true,
          },
          proposal: proposal("p-1", "CONFIRMED"),
        },
        { id: 6, kind: "user", created_at: "", text: "ẩn", hidden: true },
      ],
    };
    const state = chatReducer(initialChat, { type: "history", conversation });
    expect(state.turns.map((t) => t.user)).toEqual(["Khám da liễu thứ Bảy", "Đặt 8 giờ", null]);
    expect(state.turns[0]?.slots).toEqual([slot]);
    expect(state.turns[0]?.texts).toEqual(["Còn các khung sau."]);
    expect(state.turns[1]?.proposals[0]?.status).toBe("CONFIRMED");
    expect(state.remaining).toBe(47);
  });
});

describe("chữ hiển thị", () => {
  it("đếm ngược phút:giây, không âm", () => {
    expect(formatCountdown(581_000)).toBe("09:41");
    expect(formatCountdown(500)).toBe("00:01");
    expect(formatCountdown(-5)).toBe("00:00");
    expect(msLeft("2026-10-10T09:10:00+07:00", Date.parse("2026-10-10T09:00:19+07:00"))).toBe(
      581_000,
    );
  });

  it("rút gọn tên bác sĩ như nút khung giờ của thiết kế", () => {
    expect(shortDoctor("ThS. BS. Trần Minh")).toBe("BS. Minh");
    expect(shortDoctor("BS.CKI Nguyễn Thu Hà")).toBe("BS. Hà");
  });

  it("bỏ dấu nhấn Markdown trong câu trả lời", () => {
    expect(plainText("Còn **08:00** và **08:20**\n## Ghi chú")).toBe("Còn 08:00 và 08:20\nGhi chú");
  });
});
