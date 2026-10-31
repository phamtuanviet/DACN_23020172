// Khung chat: panel 420px bên phải trên máy tính, toàn màn hình trên điện thoại (thiết kế
// AI-desktop, AI-states; docs mục 9.5, 9.6). Trang phía sau vẫn cuộn và bấm được trên máy tính.
import Link from "next/link";
import { useEffect, useRef, useState, type KeyboardEvent, type SyntheticEvent } from "react";

import { CLINIC, TEXT } from "@/shared/texts";
import { cn } from "@/shared/lib/cn";
import { formatPrice } from "@/shared/lib/format";
import { Spinner } from "@/shared/ui/spinner";
import {
  AlertIcon,
  CalendarPlusIcon,
  ChatIcon,
  CheckIcon,
  CloseIcon,
  HeadsetIcon,
  RefreshIcon,
  SearchIcon,
  SendIcon,
  ShieldIcon,
} from "@/shared/ui/icons";

import { ProposalCard } from "./proposal-card";
import type { ServiceOption, SlotOption, Turn } from "./reducer";
import type { AgentChat } from "./use-agent-chat";

const T = TEXT.agent;
const MAX_LENGTH = 1000;
const STARTER_ICONS = [CalendarPlusIcon, RefreshIcon, SearchIcon, HeadsetIcon];

/** Mô hình đôi khi vẫn trả Markdown: bỏ dấu nhấn ** để chữ hiện sạch. */
export function plainText(text: string): string {
  return text.replace(/\*\*(.+?)\*\*/g, "$1").replace(/^#{1,6}\s+/gm, "");
}

/** "ThS. BS. Trần Minh" → "BS. Minh": chỉ giữ tên gọi để vừa nút khung giờ (thiết kế AI-desktop);
 * tên đầy đủ nằm trong aria-label của nút. */
export function shortDoctor(name: string): string {
  return `BS. ${name.trim().split(/\s+/).at(-1) ?? name}`;
}

function SlotButtons({
  slots,
  onPick,
}: {
  slots: SlotOption[];
  onPick: (slot: SlotOption) => void;
}) {
  const days = new Set(slots.map((slot) => slot.label.split(",")[0]));
  return (
    <div className="grid grid-cols-2 gap-1.5">
      {slots.map((slot) => (
        <button
          key={`${slot.start_at}-${slot.doctor_id}`}
          type="button"
          onClick={() => onPick(slot)}
          aria-label={`${T.pickSlot}: ${slot.label}, ${slot.doctor_name}`}
          className="flex min-h-11 items-center justify-between gap-2 rounded-control border border-line-strong bg-surface px-2.5 text-left text-sm hover:border-primary hover:bg-primary-soft"
        >
          <span className="flex flex-col leading-tight">
            <b className="tabular-nums">{slot.start_at.slice(11, 16)}</b>
            {days.size > 1 ? (
              <span className="text-xs text-muted">{slot.label.split(",")[0]}</span>
            ) : null}
          </span>
          <span className="truncate text-muted">{shortDoctor(slot.doctor_name)}</span>
        </button>
      ))}
    </div>
  );
}

function ServiceCards({
  services,
  onPick,
}: {
  services: ServiceOption[];
  onPick: (service: ServiceOption) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      {services.map((service) => (
        <div
          key={service.id}
          className="flex flex-col gap-1 rounded-[10px] border border-line px-3 py-2.5"
        >
          <span className="flex justify-between gap-2">
            <b>{service.name}</b>
            <span className="shrink-0 text-[13px] text-muted">
              {T.minutes(service.duration_min)} · {formatPrice(service.ref_price_vnd)}
            </span>
          </span>
          <span className="text-[13px] leading-[18px] text-muted">
            {T.scope}: {service.scope_description}
          </span>
          <button
            type="button"
            onClick={() => onPick(service)}
            className="mt-1 self-start rounded-control border border-primary px-3 py-1.5 text-sm font-semibold text-primary-ink hover:bg-primary-soft"
          >
            {T.findTimes}
          </button>
        </div>
      ))}
    </div>
  );
}

function TurnView({ turn, chat, last }: { turn: Turn; chat: AgentChat; last: boolean }) {
  const send = (message: string) => void chat.send(message);
  // Thiết kế: nút khung giờ nằm trong bong bóng trả lời; có khung thì không cần thẻ dịch vụ.
  const attachment = turn.slots.length ? (
    <SlotButtons
      slots={turn.slots}
      onPick={(slot) => send(T.pickSlotMessage(slot.label, slot.doctor_name))}
    />
  ) : turn.services.length ? (
    <ServiceCards
      services={turn.services}
      onPick={(service) => send(T.findTimesMessage(service.name))}
    />
  ) : null;
  const bubbles = turn.texts.length ? turn.texts : attachment ? [""] : [];
  return (
    <>
      {turn.user !== null ? (
        <p className="max-w-[82%] self-end rounded-[14px_14px_4px_14px] bg-primary px-3.5 py-2.5 break-words whitespace-pre-wrap text-white">
          {turn.user}
        </p>
      ) : null}
      {turn.tools.length ? (
        <ul className="flex flex-col gap-0.5 text-[13px] leading-[18px] text-muted">
          {turn.tools.map((step, index) => (
            <li key={`${step.name}-${index}`} className="flex items-center gap-1.5">
              {!step.done ? (
                <Spinner size={13} />
              ) : step.ok === false ? (
                <AlertIcon size={14} className="text-amber" />
              ) : (
                <CheckIcon size={14} strokeWidth={2.6} className="text-success" />
              )}
              {step.label}
            </li>
          ))}
        </ul>
      ) : null}
      {bubbles.map((text, index) => (
        <div
          key={index}
          className="flex w-fit max-w-[92%] flex-col gap-2.5 self-start rounded-[14px_14px_14px_4px] border border-line bg-surface px-3.5 py-3"
        >
          {text ? <p className="break-words whitespace-pre-wrap">{plainText(text)}</p> : null}
          {index === bubbles.length - 1 ? attachment : null}
        </div>
      ))}
      {turn.proposals.map((proposal) => (
        <ProposalCard
          key={proposal.id}
          proposal={proposal}
          onConfirm={chat.confirm}
          onReject={chat.reject}
          onRetry={send}
        />
      ))}
      {turn.error ? (
        <p
          role="alert"
          className="flex gap-2 self-start rounded-card border border-danger-line bg-danger-soft px-3.5 py-2.5 text-sm text-danger-ink"
        >
          <AlertIcon size={16} className="mt-0.5 shrink-0" />
          <span>
            {turn.error.message}{" "}
            {last ? (
              <Link href="/booking" className="font-semibold">
                {T.goToBooking}
              </Link>
            ) : null}
          </span>
        </p>
      ) : null}
    </>
  );
}

function Welcome({ name, onPick }: { name: string; onPick: (message: string) => void }) {
  return (
    <div className="flex flex-col gap-3.5">
      <p className="rounded-[14px_14px_14px_4px] border border-line bg-surface px-3.5 py-3">
        {T.greeting(name, CLINIC.name)}
      </p>
      <span className="font-semibold">{T.whatToDo}</span>
      <div className="flex flex-col gap-2">
        {T.starters.map((starter, index) => {
          const Icon = STARTER_ICONS[index] ?? ChatIcon;
          return (
            <button
              key={starter.label}
              type="button"
              onClick={() => onPick(starter.message)}
              className="flex min-h-12 items-center gap-2.5 rounded-[10px] border border-line-strong bg-surface px-3.5 text-left font-medium hover:border-primary hover:bg-primary-soft"
            >
              <Icon size={20} className="shrink-0 text-primary" />
              {starter.label}
            </button>
          );
        })}
      </div>
      <p className="flex gap-2.5 rounded-[10px] bg-amber-soft px-3.5 py-3 text-sm text-amber-ink">
        <ShieldIcon size={18} className="mt-px shrink-0 text-amber" />
        <span>{T.disclaimer}</span>
      </p>
    </div>
  );
}

function Blocked({ kind }: { kind: "quota" | "unavailable" }) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-2 rounded-card border border-amber-line bg-[#fff9ec] p-3.5 text-amber-ink"
    >
      <b>{kind === "quota" ? T.quotaTitle : T.pausedTitle}</b>
      <span className="text-sm">{T.fallbackBody}</span>
      <Link
        href="/booking"
        className="inline-flex h-10 items-center self-start rounded-control bg-primary px-3.5 text-sm font-semibold text-white hover:bg-primary-hover"
      >
        {T.goToBooking}
      </Link>
    </div>
  );
}

function ChatInput({
  disabled,
  blocked,
  onSend,
}: {
  disabled: boolean;
  blocked: boolean;
  onSend: (text: string) => void;
}) {
  const [text, setText] = useState("");
  const input = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    // Điện thoại: không tự bật bàn phím, để thấy màn chào và các lựa chọn trước.
    if (window.matchMedia("(min-width: 768px)").matches) input.current?.focus();
  }, []);

  function submit(event?: SyntheticEvent) {
    event?.preventDefault();
    const message = text.trim();
    if (!message || disabled || blocked) return;
    onSend(message);
    setText("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter gửi, Shift+Enter xuống dòng; đang gõ dấu bằng bộ gõ (IME) thì không gửi.
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) submit(event);
  }

  return (
    <form onSubmit={submit} className="flex items-end gap-2">
      <label htmlFor="agent-message" className="sr-only">
        {T.inputLabel}
      </label>
      <textarea
        id="agent-message"
        ref={input}
        rows={1}
        value={text}
        maxLength={MAX_LENGTH}
        disabled={blocked}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder={blocked ? T.placeholderBlocked : T.placeholder}
        className="field-sizing-content max-h-32 min-h-11 flex-1 resize-none rounded-[10px] border border-line-strong bg-surface px-3 py-2.5 text-[15px] disabled:bg-ground"
      />
      <button
        type="submit"
        aria-label={T.send}
        disabled={disabled || blocked || !text.trim()}
        className="flex size-11 shrink-0 items-center justify-center rounded-[10px] bg-primary text-white hover:bg-primary-hover disabled:bg-line-strong"
      >
        <SendIcon size={20} />
      </button>
    </form>
  );
}

export function ChatPanel({
  chat,
  firstName,
  onClose,
}: {
  chat: AgentChat;
  firstName: string;
  onClose: () => void;
}) {
  const { state } = chat;
  const log = useRef<HTMLDivElement>(null);
  const blocked = state.blocked === "quota" || state.available === false;
  const quotaUsed = state.remaining !== null && state.remaining <= 0;

  useEffect(() => {
    // Nội dung mới (chữ đang chạy, thẻ đề xuất) luôn hiện ở cuối khung chat.
    log.current?.scrollTo({ top: log.current.scrollHeight });
  }, [state.turns, state.streaming]);

  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const send = (message: string) => void chat.send(message);

  return (
    <aside
      aria-label={T.panelLabel}
      className="fixed inset-0 z-50 flex flex-col bg-ground md:inset-y-0 md:right-0 md:left-auto md:w-[420px] md:border-l md:border-line md:bg-surface md:shadow-[-16px_0_40px_rgba(19,38,43,0.12)]"
    >
      <header className="flex shrink-0 items-center gap-2 border-b border-line bg-surface py-2.5 pr-3 pl-4">
        <span
          aria-hidden="true"
          className="hidden size-9 shrink-0 items-center justify-center rounded-[10px] bg-ink text-white md:flex"
        >
          <ChatIcon size={20} />
        </span>
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="font-semibold">{T.title}</span>
          {state.remaining !== null && state.limit !== null ? (
            <span
              className={cn("text-[13px] leading-[18px]", quotaUsed ? "text-danger" : "text-muted")}
            >
              {quotaUsed ? T.quotaUsed(state.limit) : T.remaining(state.remaining)}
            </span>
          ) : null}
        </div>
        <button
          type="button"
          aria-label={T.staff}
          title={T.staff}
          disabled={blocked || state.streaming}
          onClick={() => send(T.staffMessage)}
          className="flex size-10 items-center justify-center rounded-control border border-line text-ink hover:border-primary hover:text-primary-ink disabled:opacity-50"
        >
          <HeadsetIcon size={18} />
        </button>
        <button
          type="button"
          aria-label={T.close}
          onClick={onClose}
          className="flex size-11 items-center justify-center rounded-control text-ink hover:bg-primary-soft"
        >
          <CloseIcon size={20} />
        </button>
      </header>

      <div
        ref={log}
        role="log"
        aria-label={T.logLabel}
        aria-live="polite"
        className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4 text-[15px] leading-[22px]"
      >
        {state.turns.length === 0 ? (
          <Welcome name={firstName} onPick={send} />
        ) : (
          state.turns.map((turn, index) => (
            <TurnView
              key={turn.key}
              turn={turn}
              chat={chat}
              last={index === state.turns.length - 1}
            />
          ))
        )}
        {state.streaming ? (
          <span className="flex items-center gap-2 text-[13px] text-muted">
            <Spinner size={13} />
            {T.thinking}
          </span>
        ) : null}
        {state.blocked ? <Blocked kind={state.blocked} /> : null}
        {!state.blocked && state.available === false ? <Blocked kind="unavailable" /> : null}
      </div>

      <div className="flex shrink-0 flex-col gap-2 border-t border-line bg-surface px-3 pt-2.5 pb-[max(14px,env(safe-area-inset-bottom))]">
        {state.turns.length > 0 && !blocked ? (
          <div className="flex flex-wrap gap-1.5 max-md:hidden">
            {T.chips.map((chip) => (
              <button
                key={chip.label}
                type="button"
                disabled={state.streaming}
                onClick={() => send(chip.message)}
                className="h-9 rounded-full border border-line-strong bg-surface px-3 text-[13px] hover:border-primary hover:text-primary-ink disabled:opacity-50"
              >
                {chip.label}
              </button>
            ))}
          </div>
        ) : null}
        <ChatInput disabled={state.streaming} blocked={blocked} onSend={send} />
        <span className="text-xs leading-4 text-muted">{T.disclaimerShort}</span>
      </div>
    </aside>
  );
}
