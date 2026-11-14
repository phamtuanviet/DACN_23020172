// Chỉ dùng trong client component. Hộp thoại đánh giá buổi khám (P-dialogs, UC20, FR-RPT-02): 1–5
// sao, nhận xét tùy chọn tối đa 500 ký tự, mỗi lịch Đã khám một lần. Nhận xét là dữ liệu cá nhân,
// chỉ gửi lên backend.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";

import { api } from "@/shared/api/client";
import { errorMessage, toApiError } from "@/shared/api/errors";
import type { Appointment, Review } from "@/shared/api/types";
import { clinicDay, formatDayFull } from "@/shared/lib/datetime";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Dialog } from "@/shared/ui/dialog";
import { inputClass } from "@/shared/ui/field";
import { StarIcon } from "@/shared/ui/icons";
import { toast } from "@/shared/ui/toast";

const T = TEXT.appointments;
const MAX_COMMENT = 500;
const STARS = [1, 2, 3, 4, 5];

function useSubmitReview() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id: number; rating: number; comment: string }): Promise<Review> => {
      const { data, error } = await api.POST("/api/v1/appointments/{appointment_id}/review", {
        params: { path: { appointment_id: input.id } },
        body: { rating: input.rating, comment: input.comment.trim() || null },
      });
      if (!data) throw toApiError(error);
      return data;
    },
    onSettled: () => client.invalidateQueries({ queryKey: ["appointments"] }),
  });
}

export function ReviewDialog({
  appointment,
  onClose,
}: {
  appointment: Appointment;
  onClose: () => void;
}) {
  const name = useId();
  const commentId = useId();
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [comment, setComment] = useState("");
  const [missing, setMissing] = useState(false);
  const submit = useSubmitReview();
  const error = submit.error ? toApiError(submit.error) : null;
  const shown = hover || rating;

  function send() {
    if (!rating) {
      setMissing(true);
      return;
    }
    submit.mutate(
      { id: appointment.id, rating, comment },
      {
        onSuccess: () => {
          toast.success(T.reviewThanks);
          onClose();
        },
      },
    );
  }

  const summary = [
    appointment.doctor.name,
    appointment.service.name,
    formatDayFull(clinicDay(appointment.start_at)),
  ].join(" · ");

  return (
    <Dialog
      open
      onClose={onClose}
      title={T.reviewTitle}
      description={summary}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {T.reviewLater}
          </Button>
          <Button onClick={send} loading={submit.isPending} loadingText={T.reviewSubmitting}>
            {T.reviewSubmit}
          </Button>
        </>
      }
    >
      <fieldset className="flex flex-col gap-1">
        <legend className="mb-1 text-sm font-semibold">{T.reviewScale}</legend>
        <div className="flex gap-1" onMouseLeave={() => setHover(0)}>
          {STARS.map((n) => (
            <label
              key={n}
              onMouseEnter={() => setHover(n)}
              className="flex size-11 cursor-pointer items-center justify-center rounded-control has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-primary"
            >
              <input
                type="radio"
                name={name}
                value={n}
                checked={rating === n}
                onChange={() => {
                  setRating(n);
                  setMissing(false);
                }}
                className="sr-only"
              />
              <span className="sr-only">{T.reviewStar(n)}</span>
              <StarIcon
                size={30}
                filled={n <= shown}
                className={n <= shown ? "text-star" : "text-muted"}
              />
            </label>
          ))}
        </div>
        <span aria-live="polite" className="text-sm text-muted">
          {rating ? T.reviewPicked(rating, T.reviewLevels[rating - 1] ?? "") : T.reviewPick}
        </span>
      </fieldset>
      {missing ? <Alert tone="danger">{T.reviewNeedStars}</Alert> : null}

      <div className="flex flex-col gap-1.5">
        <label htmlFor={commentId} className="text-sm font-semibold">
          {T.reviewComment} <span className="font-normal text-muted">{TEXT.booking.optional}</span>
        </label>
        <textarea
          id={commentId}
          rows={3}
          value={comment}
          maxLength={MAX_COMMENT}
          onChange={(event) => setComment(event.target.value)}
          aria-describedby={`${commentId}-hint`}
          className={inputClass(false, "multiline")}
        />
        <span id={`${commentId}-hint`} className="flex justify-between gap-3 text-sm text-muted">
          <span>{T.reviewCommentHint}</span>
          <span className="shrink-0 tabular-nums">
            {T.reviewCount(comment.length, MAX_COMMENT)}
          </span>
        </span>
      </div>
      {error ? <Alert tone="danger">{errorMessage(error)}</Alert> : null}
      <p className="text-sm text-muted">{T.reviewRule}</p>
    </Dialog>
  );
}
