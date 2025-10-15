# Agent System - Hệ thống Agent thông minh

Hệ thống agent đa chức năng với khả năng routing thông minh, sử dụng LangGraph + Groq + Serper.dev cho các tác vụ toán học, nghiên cứu, lập trình và OCR.

## 🚀 Master Agent - Router thông minh

### Tính năng chính
- **🧠 Semantic Routing**: Phân tích ngữ nghĩa thông minh với embedding models
- **📊 Multi-layered Analysis**: Kết hợp semantic similarity, keyword matching, và context analysis
- **🎯 Confidence Scoring**: Hiển thị độ tin cậy của quyết định routing
- **🔄 Fallback System**: Tự động chuyển sang phân tích đơn giản khi cần

### Các Agent chuyên biệt
1. **Math Agent**: Giải toán, phương trình, tính toán với realtime research
2. **Research Agent**: Nghiên cứu, tìm kiếm thông tin, tin tức realtime
3. **Code Agent**: Lập trình, debug, code review, phát triển phần mềm
4. **OCR Agent**: Xử lý ảnh, nhận dạng văn bản, scan tài liệu
5. **General Agent**: Trợ lý tổng quát cho các câu hỏi khác

## 📦 Cài đặt

### Yêu cầu
- Python 3.10+
- Cài đặt dependencies:
```bash
pip install -r requirements.txt
```

### Biến môi trường
Tạo file `.env` hoặc export trong shell:
```bash
GROQ_API_KEY="your_groq_key"
SERPER_API_KEY="your_serper_key"
```

PowerShell:
```powershell
$env:GROQ_API_KEY="your_groq_key"
$env:SERPER_API_KEY="your_serper_key"
```

## 🎯 Cách sử dụng

### Master Agent (Khuyến nghị)
```bash
# Toán học
python Agent\master_agent.py --prompt "Giải phương trình x^2 - 5x + 6 = 0"

# Nghiên cứu
python Agent\master_agent.py --prompt "Tin tức mới nhất về AI tuần này"

# Lập trình
python Agent\master_agent.py --prompt "Viết function Python tính giai thừa"

# OCR
python Agent\master_agent.py --prompt "Xử lý ảnh này bằng OCR"

# Tổng quát
python Agent\master_agent.py --prompt "Hôm nay là ngày gì?"
```

### Math Agent (Chuyên biệt)
```bash
# Bài toán trực tiếp
python Agent\math_agent.py --problem "Giải phương trình x^2 - 5x + 6 = 0"

# Từ file
python Agent\math_agent.py --problem_file problem.txt --output_file solution.md

# Tắt research
python Agent\math_agent.py --problem "Giải phương trình" --no_research
```

### Research Agent (Chuyên biệt)
```bash
python Agent\research_agent.py --question "Tin tức mới nhất về AI"
```

## 🏗️ Kiến trúc hệ thống

### Master Agent (`Agent/master_agent.py`)
- **State**: `user_prompt`, `agent_type`, `reasoning`, `confidence`, `context_analysis`
- **Nodes**: `analyze_prompt` → `route_to_agent` → `format_output`
- **Routing**: Semantic analysis + keyword matching + context analysis

### Semantic Router (`Agent/tools/semantic_router.py`)
- **Embedding Model**: `paraphrase-multilingual-MiniLM-L12-v2`
- **Scoring**: Semantic (40%) + Keyword (30%) + Context (30%)
- **Profiles**: 5 agent profiles với 20+ keywords mỗi loại

### Math Agent (`Agent/math_agent.py`)
- **State**: `problem_text`, `research_results`, `compiled_context`, `solution_text`
- **Flow**: `read_problem` → `research` → `solve` → `write_solution`
- **Research**: Serper.dev Scholar API cho tài liệu tham khảo

### Research Agent (`Agent/research_agent.py`)
- **State**: `question`, `research_results`, `compiled_context`, `answer`
- **Flow**: `research` → `solve` → `output`
- **Research**: DuckDuckGo HTML search

### Tools
- **Serper Tool** (`Agent/tools/serper_tool.py`): Serper.dev Scholar API
- **Semantic Router** (`Agent/tools/semantic_router.py`): Advanced routing logic

## 📊 Ví dụ đầu ra

### Master Agent với Math
```
🤖 Chọn agent: math (độ tin cậy: 0.34)
💭 Lý do: Tương đồng ngữ nghĩa cao
📊 Độ tin cậy: 0.34
🔍 Phân tích ngữ cảnh:
   - Mục đích: solve
   - Lĩnh vực: math
   - Độ phức tạp: medium

============================================================
🎯 Agent được chọn: MATH
💭 Lý do: Tương đồng ngữ nghĩa cao
📊 Độ tin cậy: 0.34
============================================================
=== LỜI GIẢI TOÁN ===
... lời giải chi tiết với LaTeX ...
============================================================
```

### Master Agent với Code
```
🤖 Chọn agent: code (độ tin cậy: 0.17)
💭 Lý do: Phân tích tổng hợp
⚠️ Độ tin cậy thấp, có thể cần xem xét lại
   math: 0.10 (semantic: 0.21, keyword: 0.04)
   research: 0.04 (semantic: 0.09, keyword: 0.00)
   ocr: 0.08 (semantic: 0.21, keyword: 0.00)
   code: 0.17 (semantic: 0.39, keyword: 0.06)
   general: 0.10 (semantic: 0.14, keyword: 0.05)

============================================================
🎯 Agent được chọn: CODE
💭 Lý do: Phân tích tổng hợp
📊 Độ tin cậy: 0.17
============================================================
=== CODE AGENT ===
... code solution với giải thích chi tiết ...
============================================================
```

## 🔧 Troubleshooting

### Lỗi thường gặp
1. **ModuleNotFoundError**: Chạy từ project root, đã xử lý import paths
2. **GROQ chưa cấu hình**: Export `GROQ_API_KEY` trước khi chạy
3. **SERPER chưa cấu hình**: Export `SERPER_API_KEY` cho research features
4. **Độ tin cậy thấp**: Hệ thống vẫn hoạt động, chỉ cần xem xét kỹ hơn

### Tối ưu hóa
- **Tăng confidence**: Sử dụng từ khóa chuyên môn rõ ràng
- **Research quality**: Đảm bảo `SERPER_API_KEY` hợp lệ
- **Code quality**: Sử dụng `GROQ_API_KEY` cho kết quả tốt nhất

## 📈 Roadmap

- [ ] Thêm agent chuyên biệt cho các lĩnh vực khác
- [ ] Cải thiện confidence scoring
- [ ] Thêm caching cho embedding
- [ ] Web interface cho master agent
- [ ] API endpoints cho integration


