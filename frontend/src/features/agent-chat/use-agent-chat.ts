// Giữ trạng thái hội thoại với trợ lý: gửi tin qua SSE, tải lại hội thoại, xác nhận thẻ đề xuất
// (docs mục 9.5). conversation_id nằm trong sessionStorage nên hội thoại sống trong phiên (FR-AGT-01).
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useReducer, useRef } from "react";

import { api } from "@/shared/api/client";
import { errorMessage, toApiError } from "@/shared/api/errors";
import { refreshAfterChange } from "@/shared/appointments/queries";
import { useAuthStore } from "@/shared/auth/auth-store";
import { toast } from "@/shared/ui/toast";

import { chatReducer, initialChat, type ProposalOut } from "./reducer";
import { ChatHttpError, streamChat } from "./stream";

const STORAGE_KEY = "agent.conversation";
const PROPOSAL_FAILED = "proposal_failed" as const;

function readConversation(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeConversation(id: string | null): void {
  try {
    if (id) sessionStorage.setItem(STORAGE_KEY, id);
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // trình duyệt chặn storage: hội thoại chỉ sống tới khi tải lại trang
  }
}

export type AgentChat = ReturnType<typeof useAgentChat>;

/** `active`: khung chat đang mở; lần mở đầu tiên mới hỏi trạng thái và tải lại hội thoại. */
export function useAgentChat(active: boolean) {
  const [state, dispatch] = useReducer(chatReducer, initialChat);
  const queryClient = useQueryClient();
  const status = useAuthStore((s) => s.status);
  const streaming = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const conversation = useRef<string | null>(null);
  const loaded = useRef(false);

  useEffect(() => {
    conversation.current = state.conversationId;
    if (state.conversationId) writeConversation(state.conversationId);
  }, [state.conversationId]);

  const load = useCallback(async () => {
    const statusResponse = await api.GET("/api/v1/agent/status");
    if (statusResponse.data) dispatch({ type: "status", status: statusResponse.data });
    const id = readConversation();
    if (!id) return;
    const { data } = await api.GET("/api/v1/agent/conversations/{conversation_id}/messages", {
      params: { path: { conversation_id: id } },
    });
    if (data) dispatch({ type: "history", conversation: data });
    else writeConversation(null); // hội thoại đã bị xóa hoặc không còn của người này
  }, []);

  useEffect(() => {
    if (status === "anonymous") {
      // Đăng xuất: dừng lượt đang chạy và bỏ hội thoại của phiên cũ.
      controller.current?.abort();
      writeConversation(null);
      conversation.current = null;
      loaded.current = false;
      dispatch({ type: "reset" });
      return;
    }
    if (active && status === "authenticated" && !loaded.current) {
      loaded.current = true;
      void load();
    }
  }, [active, status, load]);

  const send = useCallback(async (text: string, options: { hidden?: boolean } = {}) => {
    if (streaming.current) return;
    streaming.current = true;
    const abort = new AbortController();
    controller.current = abort;
    dispatch({ type: "send", text: options.hidden ? null : text });
    const onEvent = (name: string, data: unknown) => dispatch({ type: "event", name, data });
    const body = () => ({
      conversation_id: conversation.current,
      message: text,
      trigger: options.hidden ? PROPOSAL_FAILED : null,
    });
    try {
      try {
        await streamChat(body(), onEvent, abort.signal);
      } catch (error) {
        // Hội thoại cũ đã bị dọn (quá hạn lưu): bắt đầu hội thoại mới với cùng câu hỏi.
        if (!(error instanceof ChatHttpError) || error.status !== 404 || !conversation.current) {
          throw error;
        }
        writeConversation(null);
        conversation.current = null;
        await streamChat(body(), onEvent, abort.signal);
      }
    } catch (error) {
      if (!abort.signal.aborted) {
        dispatch({
          type: "failed",
          error: error instanceof ChatHttpError ? error.error : toApiError(null),
        });
      }
    } finally {
      streaming.current = false;
      dispatch({ type: "event", name: "done", data: null });
    }
  }, []);

  const reject = useCallback(async (proposal: ProposalOut) => {
    const { data, error } = await api.POST("/api/v1/agent/proposals/{proposal_id}/reject", {
      params: { path: { proposal_id: proposal.id } },
    });
    if (data) dispatch({ type: "proposal", proposal: data });
    else toast.error(errorMessage(toApiError(error)));
  }, []);

  const confirm = useCallback(
    async (proposal: ProposalOut) => {
      const { data, error } = await api.POST("/api/v1/agent/proposals/{proposal_id}/confirm", {
        params: { path: { proposal_id: proposal.id } },
      });
      if (data) {
        dispatch({ type: "proposal", proposal: data.proposal });
        void refreshAfterChange(queryClient); // "Lịch của tôi" và khung trống cập nhật ngay
        return;
      }
      const apiError = toApiError(error);
      const next = apiError.details?.proposal_status;
      if (next === "FAILED" || next === "EXPIRED") {
        dispatch({
          type: "proposal",
          proposal: {
            ...proposal,
            status: next,
            error: next === "FAILED" ? apiError.message : null,
          },
        });
      } else if (apiError.code === "PROPOSAL_NOT_PENDING") {
        loaded.current = false;
        void load(); // đã xử lý ở thẻ khác: lấy trạng thái mới nhất
      } else {
        toast.error(errorMessage(apiError));
      }
      if (apiError.code === "SLOT_TAKEN") {
        // UC09 8a: khung vừa bị đặt → lượt ẩn để trợ lý tự tìm khung mới.
        void refreshAfterChange(queryClient);
        void send(apiError.message, { hidden: true });
      }
    },
    [queryClient, load, send],
  );

  return { state, send, confirm, reject };
}
