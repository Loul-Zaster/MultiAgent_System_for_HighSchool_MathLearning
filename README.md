# Hệ thống Multi-Agent hỗ trợ học Toán THPT

Hệ thống multi‑agent hỗ trợ giải toán, nghiên cứu, tổng quát, và OCR. Master Agent định tuyến thông minh bằng semantic routing, chấm điểm độ tin cậy và fallback an toàn. Ứng dụng có giao diện Streamlit, tích hợp Notion qua MCP để đọc/ghi nội dung bài toán, và bộ nhớ dài hạn dựa trên Qdrant chạy in‑memory.

### Điểm nổi bật
- **🧠 Semantic Routing**: Kết hợp semantic embeddings + keyword + context (AI) để chọn agent phù hợp.
- **📊 Confidence Scoring & Phân tích ngữ cảnh**: Hiển thị lý do, điểm, và phân rã điểm theo từng tiêu chí.
- **🔁 Fallback an toàn**: Tự chuyển sang chiến lược đơn giản khi router/LLM lỗi.
- **🧮 Math Agent**: Giải toán theo bước, có thể tham chiếu web (Serper.dev Scholar) và xuất LaTeX.
- **🔎 Research Agent**: Tìm kiếm/biên soạn thông tin, trích xuất nguồn.
- **🖼️ OCR Agent**: Gửi ảnh tới OCR server bên ngoài, định dạng lại text/LaTeX, tùy chọn ghi Notion.
- **🧠 Memory**: Qdrant in‑memory + embeddings để lưu/tra cứu kiến thức, lời giải, nghiên cứu.
- **🧩 MCP + Notion**: Đọc bài toán từ Notion, ghi lại kết quả/trả lời vào trang Notion.
- **💬 UI**: Giao diện Streamlit giàu UX, hỗ trợ chat, LaTeX (KaTeX), và điều khiển MCP.

---

## Cấu trúc dự án
```
PROJECT/
├── Agent/
│   ├── master_agent.py        # Master router (LangGraph) + Registry các agent
│   ├── math_agent.py          # Math Agent (LangGraph + Groq + Serper)
│   ├── research_agent.py      # Research Agent
│   ├── ocr.py                 # OCR Agent (client tới OCR server)
│   └── tools/
│       ├── semantic_router.py # Semantic routing (SentenceTransformers + Groq)
│       ├── llm_router.py      # Trình kết hợp/tiện ích router (nếu dùng)
│       └── serper_tool.py     # Serper.dev Scholar API
├── Memory/
│   ├── long_term.py           # Trình quản lý bộ nhớ dài hạn (async API)
│   ├── qdrant_store.py        # Qdrant in‑memory + EmbeddingService
│   └── short_term.py          # Bộ nhớ ngắn hạn hội thoại
├── MCP/
│   ├── mcp_server.py          # MCP server kết nối Notion
│   ├── main.py                # Trình khởi động MCP server
│   ├── notion_mcp_client.py   # Client dùng trong app/agents
│   └── markdown_converter.py  # Hỗ trợ chuyển Markdown cho Notion
├── OCR/                       # Client tương tác OCR server
├── utils/
│   └── embeddings.py          # Dịch vụ tạo embedding (phù hợp Config)
├── app.py                     # Ứng dụng Streamlit giao diện chat + Notion + Agents
├── config.py                  # Cấu hình hệ thống (Qdrant, Embedding, Logging,…)
├── requirements.txt           # Thư viện chính
└── README.md                  # Tài liệu này
```

---

## Yêu cầu hệ thống
- Python 3.10+
- Windows PowerShell hoặc bash
- Internet cho Groq/Serper và OCR/Notion (nếu dùng)

## Cài đặt
```bash
# 1) Tạo môi trường (khuyến nghị)
python -m venv .venv
.\.venv\Scripts\activate   # Windows PowerShell

# 2) Cài thư viện
pip install -r requirements.txt

# 3) (Tùy chọn) Cài thêm các gói phụ thuộc cho app/UI/Notion/OCR
pip install streamlit google-generativeai python-dotenv qdrant-client loguru
```

## Biến môi trường
Tạo file `.env` tại thư mục gốc hoặc export trong shell.

Tối thiểu cho Agents:
```bash
# Groq cho LLM (general/math)
GROQ_API_KEY=your_groq_key

# Serper (Math research) – có thể bỏ qua nếu không cần web research
SERPER_API_KEY=your_serper_key
```

Cho ứng dụng Streamlit và MCP/Notion/OCR (app.py):
```bash
# Google Generative AI (dùng trong app.py)
GOOGLE_API_KEY_1=your_google_api_key

# Notion
NOTION_TOKEN=your_notion_integration_token
```

PowerShell (ví dụ):
```powershell
$env:GROQ_API_KEY="your_groq_key"
$env:SERPER_API_KEY="your_serper_key"
$env:GOOGLE_API_KEY_1="your_google_api_key"
$env:NOTION_TOKEN="your_notion_token"
```

Lưu ý bộ nhớ: `Memory/qdrant_store.py` sử dụng `QdrantClient(":memory:")` nên KHÔNG cần cài Qdrant server ngoài khi chạy cục bộ.

---

## Chạy nhanh (CLI)
### Master Agent (khuyến nghị)
```bash
python Agent\master_agent.py --prompt "Giải phương trình x^2 - 5x + 6 = 0"
python Agent\master_agent.py --prompt "Tin tức mới nhất về AI tuần này"
python Agent\master_agent.py --prompt "Hôm nay là ngày gì?"
```

### Math Agent (độc lập)
```bash
python Agent\math_agent.py --problem "Giải phương trình x^2 - 5x + 6 = 0"
python Agent\math_agent.py --problem_file problem.txt --output_file solution.md
python Agent\math_agent.py --problem "Giải phương trình" --no_research
```

### Research Agent (độc lập)
```bash
python Agent\research_agent.py --question "Tin tức mới nhất về AI"
```

### OCR Agent (qua Master)
```bash
python Agent\master_agent.py --prompt "OCR D:\\path\\to\\image.png"
```

---

## Ứng dụng giao diện (Streamlit)
Ứng dụng UI giàu tính năng tại `app.py` (yêu cầu `GOOGLE_API_KEY_1` và `NOTION_TOKEN`).

```bash
streamlit run app.py
```

Tính năng chính trong UI:
- Kết nối MCP server Notion tự động (nút Kết nối/Ngắt/Refresh bên panel trái).
- Đọc bài toán từ một Notion Page ID, phân tách các bài, chọn bài để tạo context cho Math Agent.
- Chat hiển thị LaTeX (KaTeX), lưu trao đổi lại Notion (nếu có Page ID).
- Panel phải hiển thị trạng thái Agent, bộ nhớ, thống kê.

---

## Kiến trúc định tuyến & bộ nhớ
- `Agent/tools/semantic_router.py`: 
  - Model embedding: `paraphrase-multilingual-MiniLM-L12-v2`.
  - Điểm tổng hợp = 0.4 semantic + 0.3 keyword + 0.3 context (AI via Groq).
  - Xuất chi tiết điểm theo từng agent (math/research/ocr/general).
- `Memory/long_term.py` + `Memory/qdrant_store.py`:
  - Lưu và tìm kiếm memory theo embedding (Qdrant in‑memory), API async.
  - Hỗ trợ lưu lời giải toán, nghiên cứu (kèm nguồn), tri thức tổng quát.
- `Agent/master_agent.py`:
  - LangGraph: `analyze_prompt` → `route_to_agent` → `format_output`.
  - Registry gọi các agent chuyên biệt; nối ngữ cảnh ngắn hạn/dài hạn.

---

## OCR
- Client `Agent/ocr.py` gọi tới OCR server (URL cấu hình trong code, ví dụ qua ngrok).
- Kết quả được định dạng (kể cả block LaTeX) và có thể ghi vào Notion nếu có `NOTION_TOKEN`.
- Khi gọi qua Master, hãy truyền prompt có chứa đường dẫn ảnh hợp lệ.

---

## Troubleshooting
- ModuleNotFoundError: Hãy chạy lệnh từ thư mục gốc dự án.
- Thiếu khóa: Đảm bảo `.env` có `GROQ_API_KEY`, `SERPER_API_KEY` (nếu dùng research), `GOOGLE_API_KEY_1`, `NOTION_TOKEN` (app).
- Router yếu/điểm thấp: Dùng từ khóa rõ ràng; tăng chất lượng prompt; có thể vẫn hoạt động nhưng cần xem xét kết quả.
- OCR lỗi: Kiểm tra đường dẫn ảnh, OCR server (URL), và `NOTION_TOKEN` khi ghi Notion.
- Bộ nhớ: Qdrant chạy in‑memory, dữ liệu sẽ mất khi dừng tiến trình.

---

## Roadmap đề xuất
- [ ] Thêm UI upload OCR trực tiếp trong `app.py` (đã có khung code comment).
- [ ] Cải tiến scoring router; hiển thị biểu đồ điểm.
- [ ] Caching embeddings và offline mode cho research.
- [ ] API REST cho Master Agent.
- [ ] Lưu bộ nhớ ra file/on‑disk Qdrant cho persistence.

---

## Tài liệu thêm
- Chi tiết về agents và ví dụ: xem `Agent/README.md`.
- Thư viện chính: `requirements.txt`. App UI và MCP cần thêm: `streamlit`, `google-generativeai`, `qdrant-client`, `loguru`.

Nếu cần hỗ trợ, mở issue kèm log và phiên bản Python/OS.
