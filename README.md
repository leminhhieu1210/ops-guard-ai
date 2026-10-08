# Gold Beauty Spa Operations Automation Agent

AI agent tự động hoá quy trình hỗ trợ khách hàng cho thương hiệu Gold Beauty Spa. Agent tra cứu dữ liệu thực, đối chiếu chính sách công ty, thực hiện hành động an toàn tự động và chuyển tiếp hành động nhạy cảm cho người phê duyệt.

> **AI Demo Challenge** — Option 3 (Operations Automation Agent)

---

## Kiến Trúc

```
Tin nhắn khách hàng
       │
       ▼
┌───────────────────────────────────────────────┐
│              Agent Orchestrator               │
│                                               │
│  1. RAG Engine   → truy xuất chính sách       │
│  2. LLM          → phân tích + lập kế hoạch   │
│  3. Tools        → tra cứu dữ liệu + thực thi │
│  4. Policy Engine → kiểm tra quyền thực thi   │
│  5. LLM          → tạo phản hồi               │
└───────────────────────────────────────────────┘
       │                    │
       ▼                    ▼
  Tự động thực hiện    Chuyển tiếp
  (hành động an toàn)  (cần phê duyệt)
```

| Thành phần | Vai trò | File |
|-----------|---------|------|
| Agent Orchestrator | Điều phối toàn bộ luồng xử lý | `agent/orchestrator.py` |
| RAG Engine | Truy xuất chính sách từ knowledge base | `rag/engine.py` |
| Tool System | Tools cho LLM tra cứu và thực thi | `tools/` |
| Policy Engine | Guardrails bằng rulebases | `policy/engine.py` |
| Mock Database | Dữ liệu giả lập (JSON in-memory) | `tools/mock_db.py` |
| Knowledge Base | Chính sách công ty (markdown) | `knowledge/` |

Chi tiết kiến trúc: xem [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Cách Chạy

### Yêu cầu
- Python 3.10+
- OpenAI API key

### Cài đặt

```bash
git clone <https://github.com/leminhhieu1210/ops-guard-ai.git>
cd ops-agent

python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\Activate.ps1

pip install -r requirements.txt

```

### Chạy

```bash
# Web UI
streamlit run main.py
```

---

## Kịch Bản Test

| Kịch bản | Input | Kết quả mong đợi |
|----------|-------|-------------------|
| Giao hàng trễ | "Đơn #ORD-1001 trễ 5 ngày" | Tra order → xác nhận trễ → tạo ticket |
| Hoàn tiền nhỏ | "Bị tính trùng 90.000đ đơn #ORD-1002" | Policy duyệt (< 500k) → hoàn tự động |
| Hoàn tiền lớn | "Bị tính trùng 2.640.000đ đơn #ORD-1003" | Policy chặn (≥ 500k) → chuyển tiếp |
| Huỷ gói đăng ký | "Huỷ gói Premium, mã C001" | Huỷ + đề xuất ưu đãi giữ chân |
| Đe dọa pháp lý | "Tôi sẽ kiện nếu không hoàn tiền" | Escalation CRITICAL ngay lập tức |
| Đơn không tồn tại | "Trạng thái đơn #ORD-9999?" | Thông báo không tìm thấy |
| Hỏi chính sách | "Chính sách hoàn tiền là gì?" | RAG truy xuất → tóm tắt kèm citation |

---

## Cấu Trúc Dự Án

```
├── main.py                  # Streamlit Web UI
├── config.py                # Cấu hình tập trung
├── agent/
│   ├── orchestrator.py      # Vòng lặp agent chính
│   └── prompts.py           # System prompt
├── tools/
│   ├── registry.py          # Tool schemas + dispatch
│   ├── handlers.py          # Tool implementations
│   └── mock_db.py           # Mock database (JSON)
├── rag/
│   └── engine.py            # ChromaDB retrieval
├── policy/
│   └── engine.py            # Guardrails (code)
├── data/                    # Mock data (JSON)
└── knowledge/               # Knowledge base (markdown)
```

---

## Tech Stack

- **Python 3.10+**
- **OpenAI API** (GPT-4o-mini)
- **ChromaDB** — vector database local
- **sentence-transformers** — embedding local (`all-MiniLM-L6-v2`)
- **Streamlit** — web UI
