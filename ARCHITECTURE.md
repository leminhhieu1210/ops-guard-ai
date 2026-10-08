# Kiến Trúc Hệ Thống

## 1. Tổng Quan

Hệ thống AI agent tự động hoá quy trình hỗ trợ khách hàng cho thương hiệu Gold Beauty Spa. Agent nhận tin nhắn khách hàng, tra cứu dữ liệu, đối chiếu chính sách, thực hiện hành động an toàn tự động và chuyển tiếp hành động nhạy cảm cho người phê duyệt.

```
Tin nhắn khách hàng
       │
       ▼
┌───────────────────────────────────────────────┐
│               Agent Orchestrator              │
│                                               │
│  1. RAG Engine    → truy xuất chính sách      │
│  2. LLM           → phân tích + lập kế hoạch  │
│  3. Tools         → tra cứu dữ liệu + thực thi│
│  4. Policy Engine → kiểm tra quyền thực thi   │
│  5. LLM           → tạo phản hồi              │
└───────────────────────────────────────────────┘
       │                    │
       ▼                    ▼
  Tự động thực hiện    Chuyển tiếp
  (hành động an toàn)  (cần phê duyệt)
```

---

## 2. Các Thành Phần

### 2.1 Agent Orchestrator (`agent/orchestrator.py`)

Điều phối toàn bộ luồng xử lý. Chạy vòng lặp agentic: LLM đề xuất tool → Policy Engine kiểm tra → thực thi hoặc chặn → LLM nhận kết quả → lặp lại cho đến khi có phản hồi cuối. Giới hạn tối đa 5 tool calls/lượt.

### 2.2 Policy Engine (`policy/engine.py`)

Guardrails bằng code rulebases. LLM quyết định hành động, Policy Engine quyết định quyền thực thi.

Thứ tự kiểm tra:
1. Đe dọa pháp lý → CRITICAL
2. Số tiền ≥ 500.000đ → HIGH
3. Hoàn tiền quá nhiều lần trong 90 ngày → MEDIUM
4. Ngoài thời hạn 30 ngày → MEDIUM
5. Tất cả pass → LOW (tự động duyệt)

### 2.3 RAG Engine (`rag/engine.py`)

Truy xuất chính sách công ty từ knowledge base (5 file markdown) bằng vector search.

- Chunking theo heading `##`, mỗi chunk mang metadata (file nguồn, tên section) để trích dẫn.
- Embedding: `sentence-transformers` (`all-MiniLM-L6-v2`), chạy local. Fallback hash-based khi không tải được model.
- Storage: ChromaDB persistent, chạy local.

### 2.4 Tool System (`tools/`)

8 tools định nghĩa bằng OpenAI function-calling schema. Kiến trúc 3 tầng:

```
Registry (schema + dispatch)  →  Handler (validate + logic)  →  MockDB (đọc/ghi JSON)
```

| Tool | Loại | Policy |
|------|------|--------|
| `get_customer`, `get_order`, `get_orders_by_customer`, `get_subscription` | Read-only | Luôn cho phép |
| `create_support_ticket`, `send_notification` | Write (an toàn) | Luôn cho phép |
| `process_refund` | Write (nhạy cảm) | Kiểm tra ngưỡng, thời hạn, đe dọa |
| `cancel_subscription` | Write (nhạy cảm) | Kiểm tra đe dọa pháp lý |

### 2.5 Prompts (`agent/prompts.py`)

System prompt tiếng Việt định nghĩa vai trò, nguyên tắc, quy tắc cho agent. RAG context được gộp vào cùng system message (một số LLM server yêu cầu system message duy nhất ở đầu).

---

## 3. Luồng Xử Lý

Ví dụ: *"Em bị tính tiền trùng 90.000đ cho đơn #ORD-1002"*

| Bước | Thành phần | Hành động | Kết quả |
|------|-----------|-----------|---------|
| 1 | RAG | Truy xuất chính sách | `refund_policy.md → Hoàn Tiền Tự Động` |
| 2 | LLM | Gọi `get_order("ORD-1002")` | — |
| 3 | Policy | Kiểm tra | Read-only → cho phép |
| 4 | Tool | Thực thi | `{double_charged, 2 × 90.000đ}` |
| 5 | LLM | Gọi `process_refund("ORD-1002", 90000)` | — |
| 6 | Policy | Kiểm tra | 90k < 500k, trong 30 ngày → cho phép |
| 7 | Tool | Thực thi | Hoàn tiền thành công |
| 8 | LLM | Tạo phản hồi cho khách | Kèm citation nguồn chính sách |

---

## 4. Xử Lý Lỗi

| Tình huống | Xử lý |
|------------|-------|
| Đơn hàng không tồn tại | Tool trả `{found: false}`, LLM yêu cầu thêm thông tin |
| Tham số tool không hợp lệ | ToolRegistry bắt `TypeError`, trả error cho LLM |
| LLM gọi tool liên tục | `MAX_TOOL_CALLS_PER_TURN = 5` cắt vòng lặp |
| Policy chặn hành động | Tạo escalation, LLM tạo ticket thay thế |
| RAG không có kết quả | Agent không đưa ra quyết định về chính sách, thông báo thiếu thông tin và chuyển tiếp |
| Không tải được embedding model | Fallback hash-based embedding |

---

## 5. Cải Tiến Cho Production

**Ngắn hạn:** PostgreSQL, conversation memory (Redis), Slack webhook cho escalation, structured logging.

**Trung hạn:** Hybrid RAG (vector + BM25), cross-encoder re-ranking, evaluation suite với golden Q&A pairs, rate limiting.

**Dài hạn:** Multi-agent (router → specialist agents), human feedback loop, fine-tune model, analytics dashboard.

---

## 6. Tech Stack

| Thành phần | Công nghệ |
|-----------|-----------|
| LLM | OpenAI API (GPT-4o-mini) |
| Vector DB | ChromaDB (local) |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`, local) |
| Web UI | Streamlit |
| Language | Python 3.10+ |
