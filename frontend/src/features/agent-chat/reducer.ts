// Trạng thái khung chat dựng từ sự kiện SSE (docs mục 8.4) hoặc từ hội thoại tải lại (mục 9.5).
// Hàm thuần, không gọi API, để test được bằng unit test.
import type { ApiError } from "@/shared/api/errors";
import type { components } from "@/shared/api/schema";

type Schemas = components["schemas"];
export type ProposalOut = Schemas["ProposalOut"];
export type SlotOption = Schemas["SlotOption"];
export type ServiceOption = Schemas["ServiceOption"];
export type AgentStatus = Schemas["AgentStatus"];
export type Conversation = Schemas["ConversationOut"];
export type ChatRequest = Schemas["ChatRequest"];

export type ToolStep = { name: string; label: string; done: boolean; ok: boolean | null };

/** Một lượt: câu người dùng nói và mọi thứ trợ lý làm sau đó, hiện theo thiết kế AI-desktop. */
export type Turn = {
  key: string;
  user: string | null; // null: lượt tự gửi sau đề xuất thất bại, hoặc phần mở đầu bị cắt
  tools: ToolStep[];
  texts: string[]; // các bong bóng trả lời; công cụ chạy xen giữa thì sang bong bóng mới
  slots: SlotOption[];
  services: ServiceOption[];
  proposals: ProposalOut[];
  error: { code: string; message: string } | null;
  split: boolean; // vừa có tool chạy: chữ tiếp theo mở bong bóng mới
};

export type Blocked = "quota" | "unavailable" | null;

export type ChatState = {
  conversationId: string | null;
  turns: Turn[];
  streaming: boolean;
  remaining: number | null;
  limit: number | null;
  available: boolean | null; // null: chưa hỏi backend
  blocked: Blocked;
};

export type ChatAction =
  | { type: "status"; status: AgentStatus }
  | { type: "history"; conversation: Conversation }
  | { type: "send"; text: string | null }
  | { type: "event"; name: string; data: unknown }
  | { type: "failed"; error: ApiError }
  | { type: "proposal"; proposal: ProposalOut }
  | { type: "reset" };

export const initialChat: ChatState = {
  conversationId: null,
  turns: [],
  streaming: false,
  remaining: null,
  limit: null,
  available: null,
  blocked: null,
};

let turnSeq = 0;

function newTurn(user: string | null): Turn {
  turnSeq += 1;
  return {
    key: `turn-${turnSeq}`,
    user,
    tools: [],
    texts: [],
    slots: [],
    services: [],
    proposals: [],
    error: null,
    split: false,
  };
}

function updateLast(state: ChatState, update: (turn: Turn) => Turn): ChatState {
  const last = state.turns.at(-1) ?? newTurn(null);
  return { ...state, turns: [...state.turns.slice(0, -1), update(last)] };
}

function addText(turn: Turn, text: string): Turn {
  if (turn.split || turn.texts.length === 0) {
    return { ...turn, texts: [...turn.texts, text], split: false };
  }
  const texts = [...turn.texts];
  texts[texts.length - 1] += text;
  return { ...turn, texts };
}

/** Thẻ mới thay thẻ cũ đang chờ trong cùng hội thoại (backend chuyển thẻ cũ sang EXPIRED). */
function placeProposal(state: ChatState, proposal: ProposalOut): ChatState {
  const turns = state.turns.map((turn) => ({
    ...turn,
    proposals: turn.proposals.map((p) =>
      p.id !== proposal.id && p.status === "PENDING" ? { ...p, status: "EXPIRED" as const } : p,
    ),
  }));
  return updateLast({ ...state, turns }, (turn) => ({
    ...turn,
    proposals: [...turn.proposals.filter((p) => p.id !== proposal.id), proposal],
  }));
}

function applyEvent(state: ChatState, name: string, data: unknown): ChatState {
  const payload = (data ?? {}) as Record<string, unknown>;
  switch (name) {
    case "meta":
      return { ...state, conversationId: String(payload.conversation_id) };
    case "token":
      return updateLast(state, (turn) => addText(turn, String(payload.text ?? "")));
    case "tool": {
      const step = payload as { name: string; status: string; label: string; ok?: boolean };
      return updateLast(state, (turn) => {
        if (step.status === "start") {
          const tools = [
            ...turn.tools,
            { name: step.name, label: step.label, done: false, ok: null },
          ];
          return { ...turn, tools, split: true };
        }
        const index = turn.tools.findLastIndex((t) => t.name === step.name && !t.done);
        const done = { name: step.name, label: step.label, done: true, ok: step.ok ?? null };
        const tools =
          index >= 0 ? turn.tools.map((t, i) => (i === index ? done : t)) : [...turn.tools, done];
        return { ...turn, tools, split: true };
      });
    }
    case "slots":
      return updateLast(state, (turn) => ({ ...turn, slots: payload.slots as SlotOption[] }));
    case "services":
      return updateLast(state, (turn) => ({
        ...turn,
        services: payload.services as ServiceOption[],
      }));
    case "proposal":
      return placeProposal(state, data as ProposalOut);
    case "error":
      return updateLast(state, (turn) => ({
        ...turn,
        error: { code: String(payload.code), message: String(payload.message) },
      }));
    case "done":
      return {
        ...state,
        streaming: false,
        remaining:
          typeof payload.remaining_quota === "number" ? payload.remaining_quota : state.remaining,
      };
    default:
      return state;
  }
}

/** Hội thoại tải lại → các lượt: mỗi tin USER mở một lượt mới. */
export function turnsFromHistory(conversation: Conversation): Turn[] {
  const turns: Turn[] = [];
  const current = (): Turn => {
    const last = turns.at(-1);
    if (last) return last;
    const turn = newTurn(null);
    turns.push(turn);
    return turn;
  };
  for (const item of conversation.items) {
    if (item.kind === "user") {
      turns.push(newTurn(item.hidden ? null : (item.text ?? "")));
      continue;
    }
    const turn = current();
    if (item.kind === "assistant") {
      turn.texts.push(item.text ?? "");
      turn.split = false;
      continue;
    }
    if (item.tool) {
      const { name, label, ok } = item.tool;
      turn.tools.push({ name, label, done: true, ok: ok ?? null });
    }
    if (item.services?.length) turn.services = item.services;
    if (item.slots?.length) turn.slots = item.slots;
    if (item.proposal) turn.proposals.push(item.proposal);
    turn.split = true;
  }
  return turns;
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "status":
      return {
        ...state,
        available: action.status.available,
        remaining: action.status.remaining_quota,
        limit: action.status.daily_limit,
        blocked: action.status.remaining_quota <= 0 ? "quota" : null,
      };
    case "history":
      return {
        ...state,
        conversationId: action.conversation.id,
        turns: turnsFromHistory(action.conversation),
        remaining: action.conversation.remaining_quota,
      };
    case "send":
      return { ...state, streaming: true, turns: [...state.turns, newTurn(action.text)] };
    case "event":
      return applyEvent(state, action.name, action.data);
    case "failed": {
      const blocked: Blocked =
        action.error.code === "AGENT_QUOTA_EXCEEDED"
          ? "quota"
          : action.error.code === "AGENT_UNAVAILABLE"
            ? "unavailable"
            : null;
      const withError = blocked
        ? state
        : updateLast(state, (turn) => ({
            ...turn,
            error: { code: action.error.code, message: action.error.message },
          }));
      return {
        ...withError,
        streaming: false,
        blocked,
        remaining: blocked === "quota" ? 0 : withError.remaining,
      };
    }
    case "proposal":
      return {
        ...state,
        turns: state.turns.map((turn) => ({
          ...turn,
          proposals: turn.proposals.map((p) => (p.id === action.proposal.id ? action.proposal : p)),
        })),
      };
    case "reset":
      return {
        ...initialChat,
        available: state.available,
        remaining: state.remaining,
        limit: state.limit,
      };
  }
}
