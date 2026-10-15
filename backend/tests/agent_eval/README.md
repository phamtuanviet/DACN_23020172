# Bộ kịch bản đánh giá Agent

Mỗi kịch bản là một file YAML trong `scenarios/` (docs mục 6.7): tin nhắn đầu vào, đồng hồ cố định,
tool và tham số mong đợi, kết quả mong đợi, kiểm tra an toàn (database không đổi khi chưa xác nhận).
Chạy với LLM thật: `uv run pytest -m agent_eval` — tốn chi phí, chỉ chạy khi đổi prompt hoặc mô hình.
