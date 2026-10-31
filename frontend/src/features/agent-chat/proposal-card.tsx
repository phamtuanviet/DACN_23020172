// Thẻ xác nhận đề xuất (thiết kế AI-desktop, AI-states 3 và 4; docs mục 9.5). Chữ trên thẻ lấy từ
// `display` do backend dựng, không phải chữ của LLM. Bấm Xác nhận gọi thẳng endpoint confirm.
import Link from "next/link";
import { useEffect, useState } from "react";

import { cn } from "@/shared/lib/cn";
import { TEXT } from "@/shared/texts";
import { Button } from "@/shared/ui/button";
import { CheckIcon, ClockIcon } from "@/shared/ui/icons";

import { formatCountdown, msLeft } from "./countdown";
import type { ProposalOut } from "./reducer";

const T = TEXT.agent;

function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active]);
  return now;
}

function Details({ proposal }: { proposal: ProposalOut }) {
  const { display } = proposal;
  if (proposal.type === "RESCHEDULE") {
    return (
      <>
        <div className="flex flex-col gap-1.5">
          <div className="rounded-control bg-ground px-3 py-2.5">
            <span className="block text-xs leading-4 text-muted">{T.oldTime}</span>
            <span className="text-muted line-through">{display.old_when}</span>
          </div>
          <div className="rounded-control bg-primary-soft px-3 py-2.5">
            <span className="block text-xs leading-4 text-primary-ink">{T.newTime}</span>
            <span className="font-bold text-primary-ink">{display.when}</span>
          </div>
        </div>
        <span className="text-sm text-muted">
          {[display.service, display.doctor, display.code ? T.keepCode(display.code) : null]
            .filter(Boolean)
            .join(" · ")}
        </span>
      </>
    );
  }
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
      <dt className="text-muted">{T.service}</dt>
      <dd>{display.service}</dd>
      <dt className="text-muted">{T.doctor}</dt>
      <dd>{display.doctor}</dd>
      <dt className="text-muted">{T.time}</dt>
      <dd className="font-semibold">{display.when}</dd>
      {display.reason ? (
        <>
          <dt className="text-muted">{T.reason}</dt>
          <dd className="break-words">{display.reason}</dd>
        </>
      ) : null}
    </dl>
  );
}

export function ProposalCard({
  proposal,
  onConfirm,
  onReject,
  onRetry,
}: {
  proposal: ProposalOut;
  onConfirm: (proposal: ProposalOut) => Promise<void>;
  onReject: (proposal: ProposalOut) => Promise<void>;
  onRetry: (message: string) => void;
}) {
  const pending = proposal.status === "PENDING";
  const now = useNow(pending);
  const [busy, setBusy] = useState<"confirm" | "reject" | null>(null);
  const left = msLeft(proposal.expires_at, now);
  const expired = proposal.status === "EXPIRED" || (pending && left <= 0);

  async function act(kind: "confirm" | "reject") {
    setBusy(kind);
    try {
      await (kind === "confirm" ? onConfirm(proposal) : onReject(proposal));
    } finally {
      setBusy(null);
    }
  }

  if (proposal.status === "CONFIRMED") {
    const code = proposal.appointment_code ?? proposal.display.code ?? "";
    return (
      <div
        role="status"
        className="flex gap-3 rounded-card border border-[#b9dfc6] bg-[#eef8f1] p-3.5"
      >
        <span
          aria-hidden="true"
          className="flex size-8 shrink-0 items-center justify-center rounded-full bg-success text-white"
        >
          <CheckIcon size={18} strokeWidth={2.8} />
        </span>
        <span className="flex min-w-0 flex-col gap-0.5">
          <b>{T.confirmed[proposal.type](code)}</b>
          <span className="text-sm">
            {proposal.display.when} · {proposal.display.doctor}
          </span>
          <Link
            href={
              proposal.appointment_id
                ? `/me/appointments?id=${proposal.appointment_id}`
                : "/me/appointments"
            }
            className="text-sm font-semibold"
          >
            {T.viewAppointments}
          </Link>
        </span>
      </div>
    );
  }

  if (expired || proposal.status === "REJECTED" || proposal.status === "FAILED") {
    const failed = proposal.status === "FAILED";
    return (
      <div
        className={cn(
          "flex flex-col gap-2 rounded-card p-3.5 text-muted",
          failed
            ? "border border-danger-line bg-danger-soft"
            : "border border-dashed border-line-strong bg-surface",
        )}
      >
        <b className={failed ? "text-danger-ink" : "text-ink"}>
          {failed ? T.failedTitle : expired ? T.expiredTitle : T.rejectedTitle}
        </b>
        <span className="text-sm text-subtle">
          {proposal.display.service} · {proposal.display.when}
        </span>
        <span className="text-sm">
          {failed ? proposal.error : expired ? T.expiredBody : T.rejectedBody}
        </span>
        {expired ? (
          <Button
            variant="secondary"
            size="sm"
            className="self-start"
            onClick={() => onRetry(T.retrySlotsMessage(proposal.display.service))}
          >
            {T.retrySlots}
          </Button>
        ) : null}
      </div>
    );
  }

  const time = formatCountdown(left);
  return (
    <section
      aria-label={T.proposalTitle[proposal.type]}
      className="flex flex-col gap-2.5 rounded-card border-[1.5px] border-primary bg-surface px-4 py-3.5"
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-[15px] leading-[22px] font-semibold">
          {T.proposalTitle[proposal.type]}
        </h3>
        <span
          role="timer"
          aria-label={T.countdownLabel(time)}
          className="flex items-center gap-1 rounded-full bg-amber-soft px-2 py-0.5 text-[13px] leading-[18px] font-semibold text-amber tabular-nums"
        >
          <ClockIcon size={13} strokeWidth={2.4} />
          {T.countdown(time)}
        </span>
      </div>
      <Details proposal={proposal} />
      <div className="flex gap-2">
        <Button
          variant="secondary"
          disabled={busy !== null}
          loading={busy === "reject"}
          onClick={() => void act("reject")}
        >
          {T.rejectLabel[proposal.type]}
        </Button>
        <Button
          variant={proposal.type === "CANCEL" ? "danger" : "primary"}
          className="flex-1"
          disabled={busy !== null}
          loading={busy === "confirm"}
          onClick={() => void act("confirm")}
        >
          {T.confirmLabel[proposal.type]}
        </Button>
      </div>
    </section>
  );
}
