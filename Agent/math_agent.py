import os
import sys
import asyncio
from typing import List, Dict, Optional
from dotenv import load_dotenv
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
from groq import Groq
import aiohttp
from bs4 import BeautifulSoup

# Ensure the project root is on sys.path for script execution
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
try:
    from Agent.tools.serper_tool import serper_scholar_search
except Exception:
    # Fallback if executed as a script from within the Agent directory
    from tools.serper_tool import serper_scholar_search

# Load environment variables first
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

#  Config 
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
groq_client: Optional[Groq] = None
if GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
    except Exception:
        groq_client = None
else:
    groq_client = None


#  State 
class MathAgentState(BaseModel):
    problem_text: str = ""
    research_results: List[Dict[str, str]] = []
    compiled_context: str = ""
    solution_text: str = ""
    use_research: bool = True


#  Research Tool (Serper.dev) 
async def serper_scholar_search(query: str, max_results: int = 6, timeout_seconds: int = 12, gl: str = "vn", hl: str = "vi") -> List[Dict[str, str]]:
    if not SERPER_API_KEY:
        return []
    url = "https://google.serper.dev/scholar"
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "q": query,
        "gl": gl,
        "hl": hl,
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers, timeout=timeout_seconds) as resp:
                data = await resp.json(content_type=None)
        except Exception:
            return []

    results: List[Dict[str, str]] = []
    organic = data.get("organic") or []
    for item in organic:
        title = item.get("title") or item.get("name") or ""
        url = item.get("link") or item.get("url") or ""
        snippet = item.get("snippet") or item.get("description") or item.get("abstract") or ""
        if title and url:
            results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= max_results:
            break
    return results


async def build_compiled_context(results: List[Dict[str, str]], max_chars: int = 1800) -> str:
    lines: List[str] = []
    for idx, item in enumerate(results, start=1):
        title = item.get("title", "").strip()
        url = item.get("url", "").strip()
        snippet = item.get("snippet", "").strip()
        entry = f"[{idx}] {title}\n{url}\n{snippet}\n"
        lines.append(entry)
        if sum(len(x) for x in lines) > max_chars:
            break
    return "\n".join(lines)


#  Nodes 
async def read_problem(state: MathAgentState, problem_text: Optional[str] = None) -> MathAgentState:
    if problem_text:
        state.problem_text = problem_text
    if not state.problem_text.strip():
        raise ValueError("Không có nội dung toán để giải")
    print("📘 Problem:\n", state.problem_text)
    return state


async def research_problem(state: MathAgentState) -> MathAgentState:
    query = state.problem_text.strip()
    if not query or not state.use_research:
        return state
    # Prefer Serper Scholar for higher-quality math references; fallback none
    results = await serper_scholar_search(query, max_results=6)
    # If SERPER_API_KEY is missing or error, results may be empty
    state.research_results = results
    state.compiled_context = await build_compiled_context(results)
    print("🔎 Research results:", len(results))
    return state


async def solve_problem(state: MathAgentState) -> MathAgentState:
    if groq_client is None:
        # Fallback if GROQ not configured
        ctx = f"\n\nNguồn tham khảo (nếu có):\n{state.compiled_context}" if state.compiled_context else ""
        state.solution_text = "(GROQ chưa cấu hình)\n" + state.problem_text + ctx
        print("Solution (fallback) ready")
        return state

    system_prompt = (
        "Bạn là trợ lý giải toán chi tiết và chính xác. BẮT BUỘC sử dụng LaTeX thực sự cho mọi công thức toán học.\n\n"
        "=== QUY TẮC BẮT BUỘC ===\n"
        "1. Mọi công thức toán học PHẢI được viết bằng LaTeX với delimiters $ (inline) hoặc $$ (display).\n"
        "2. TUYỆT ĐỐI KHÔNG sử dụng bất kỳ placeholder nào như LATEXINLINE, LATEXDISPLAY, hoặc bất kỳ biến thể nào.\n"
        "3. Nếu bạn viết bất kỳ placeholder nào, đó là LỖI NGHIÊM TRỌNG và câu trả lời sẽ bị từ chối.\n\n"
        "=== VÍ DỤ CÁCH VIẾT ĐÚNG (LÀM THEO ĐÚNG FORMAT NÀY) ===\n"
        "Ví dụ 1 - Tính toán đơn giản:\n"
        "Tổng khối lượng là $1 \\times 5 + 2 \\times 2 + 3 \\times 3 = 5 + 4 + 9 = 18$ kg.\n\n"
        "Ví dụ 2 - Công thức phức tạp:\n"
        "Khối lượng trung bình được tính bằng:\n"
        "$$\\bar{x} = \\frac{1 \\times 5 + 2 \\times 2 + 3 \\times 3}{10} = \\frac{18}{10} = 1.8$$\n\n"
        "Ví dụ 3 - Xác suất:\n"
        "Xác suất chọn quả có khối lượng 1 là $P(X = 1) = \\frac{5}{10} = 0.5$.\n\n"
        "Ví dụ 4 - Kỳ vọng:\n"
        "Kỳ vọng của biến ngẫu nhiên X là:\n"
        "$$E(X) = \\sum_{i=1}^{3} x_i \\cdot P(X = x_i) = 1 \\times 0.5 + 2 \\times 0.2 + 3 \\times 0.3 = 1.8$$\n\n"
        "=== VÍ DỤ SAI (TUYỆT ĐỐI KHÔNG LÀM NHƯ VẬY) ===\n"
        "SAI: Tổng khối lượng là LATEXINLINE4\n"
        "SAI: Xác suất LATEXDISPLAY\n"
        "SAI: Khối lượng trung bình: LATEXINLINE\n"
        "SAI: Kỳ vọng LATEXDISPLAY0\n\n"
        "=== KHI NÀO DÙNG $ VÀ KHI NÀO DÙNG $$ ===\n"
        "- Dùng $...$ cho công thức inline trong câu: Giá trị $x = 5$ hoặc $P(X = 1) = 0.5$.\n"
        "- Dùng $$...$$ cho công thức display riêng dòng:\n"
        "  $$E(X) = \\sum_{i=1}^{n} x_i \\cdot P(X = x_i)$$\n\n"
        "=== NHẮC LẠI ===\n"
        "KHÔNG BAO GIỜ viết LATEXINLINE, LATEXDISPLAY, hoặc bất kỳ placeholder nào. "
        "LUÔN viết LaTeX thực sự với $ hoặc $$.\n\n"
        "Nếu có nguồn/công thức từ web research, trích dẫn [n]. Nêu giả thiết, kết luận rõ ràng."
    )
    user_prompt = (
        f"Bài toán:\n{state.problem_text}\n\n"
        f"Web findings (indexed):\n{state.compiled_context}\n\n"
        "Lời giải chi tiết:\n\n"
        "LƯU Ý QUAN TRỌNG: Viết MỌI công thức toán học bằng LaTeX với delimiters $ hoặc $$. "
        "KHÔNG BAO GIỜ sử dụng LATEXINLINE, LATEXDISPLAY, hoặc bất kỳ placeholder nào khác. "
        "Ví dụ: Nếu tính tổng khối lượng, viết $1 \\times 5 + 2 \\times 2 + 3 \\times 3 = 18$ "
        "chứ KHÔNG viết LATEXINLINE4."
    )

    # Debug: Log the actual prompts being sent
    print("=" * 80)
    print("DEBUG: System prompt (first 500 chars):")
    print(system_prompt[:500])
    print("=" * 80)
    print("DEBUG: User prompt (first 500 chars):")
    print(user_prompt[:500])
    print("=" * 80)

    parts: List[str] = []
    try:
        completion = groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,  # Use 0 for more deterministic output
            max_completion_tokens=3000,  # Increase for longer solutions
            top_p=1,
            reasoning_effort="medium",
            stream=True,
            stop=None,
        )
        for chunk in completion:
            delta = getattr(chunk.choices[0], "delta", None)
            if delta and getattr(delta, "content", None):
                parts.append(delta.content)
        state.solution_text = "".join(parts)
        
        # Debug: Log the raw response
        print("=" * 80)
        print("DEBUG: Raw LLM response (first 1000 chars):")
        print(state.solution_text[:1000])
        print("=" * 80)
        
        # Post-processing: Check for placeholders and try to fix
        if 'LATEXINLINE' in state.solution_text.upper() or 'LATEXDISPLAY' in state.solution_text.upper():
            print("WARNING: LLM returned placeholders instead of LaTeX!")
            print(f"   Found in solution (first 500 chars): {state.solution_text[:500]}")
            
            # Try to fix by asking LLM to replace placeholders with actual LaTeX
            # Use a more aggressive fix prompt with examples
            fix_prompt = (
                f"LỜI GIẢI SAU CÓ LỖI: chứa các placeholder LATEXINLINE/LATEXDISPLAY thay vì LaTeX thực sự.\n\n"
                f"Lời giải có lỗi:\n{state.solution_text}\n\n"
                f"NHIỆM VỤ: Viết lại TOÀN BỘ lời giải, thay thế MỌI placeholder bằng LaTeX thực sự.\n\n"
                f"QUY TẮC:\n"
                f"- LATEXINLINE hoặc LATEXINLINE4 trong 'Tổng khối lượng LATEXINLINE4' → $1 \\times 5 + 2 \\times 2 + 3 \\times 3 = 18$\n"
                f"- LATEXDISPLAY hoặc LATEXDISPLAY0 trong 'Khối lượng trung bình LATEXDISPLAY0' → $$\\bar{x} = \\frac{18}{10} = 1.8$$\n"
                f"- LATEXINLINE trong 'Xác suất LATEXINLINE' → $P(X = 1) = \\frac{5}{10} = 0.5$\n"
                f"- LATEXDISPLAY trong 'Kỳ vọng LATEXDISPLAY' → $$E(X) = \\sum_{i} x_i \\cdot P(X = x_i)$$\n\n"
                f"Hãy phân tích ngữ cảnh xung quanh mỗi placeholder để suy ra công thức LaTeX đúng, rồi thay thế.\n"
                f"Viết lại TOÀN BỘ lời giải, KHÔNG để lại bất kỳ placeholder nào."
            )
            
            try:
                fix_completion = groq_client.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=[
                        {"role": "system", "content": (
                            "Bạn là chuyên gia sửa lỗi LaTeX. Nhiệm vụ của bạn là thay thế MỌI placeholder "
                            "LATEXINLINE/LATEXDISPLAY bằng LaTeX thực sự với delimiters $ hoặc $$. "
                            "Phân tích ngữ cảnh để suy ra công thức đúng. KHÔNG được để lại bất kỳ placeholder nào."
                        )},
                        {"role": "user", "content": fix_prompt},
                    ],
                    temperature=0.0,  # Use 0 for deterministic fixing
                    max_completion_tokens=3000,  # Allow longer fixes
                )
                fixed_text = fix_completion.choices[0].message.content
                if fixed_text and ('LATEXINLINE' not in fixed_text.upper() and 'LATEXDISPLAY' not in fixed_text.upper()):
                    state.solution_text = fixed_text
                    print("Fixed placeholders with actual LaTeX")
                else:
                    print("Fix attempt still contains placeholders")
                    print(f"   Fixed text preview: {fixed_text[:300] if fixed_text else 'None'}")
            except Exception as e:
                print(f"Could not fix placeholders: {e}")
        
        print("Solution generated")
    except Exception as e:
        state.solution_text = f"(GROQ error) {e}"
    return state


async def write_solution(state: MathAgentState, output_file: Optional[str] = None) -> MathAgentState:
    if not state.solution_text or not state.solution_text.strip():
        print("Không có lời giải để ghi")
        return state
    
    header = "### Lời giải:\n"
    content = header + state.solution_text
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Solution written to {output_file}")
    else:
        print("\n===== LỜI GIẢI =====\n")
        print(content)
    return state


#  Graph 
def build_graph():
    graph = StateGraph(MathAgentState)

    async def read_node(state):
        return await read_problem(state)

    async def research_node(state):
        return await research_problem(state)

    async def solve_node(state):
        return await solve_problem(state)

    async def write_node(state):
        return await write_solution(state)

    graph.add_node("read_problem", read_node)
    graph.add_node("research", research_node)
    graph.add_node("solve", solve_node)
    graph.add_node("write_solution", write_node)

    graph.add_edge("read_problem", "research")
    graph.add_edge("research", "solve")
    graph.add_edge("solve", "write_solution")
    graph.add_edge("write_solution", END)

    graph.set_entry_point("read_problem")
    return graph


#  CLI 
async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Standalone Math Agent (LangGraph + Groq + Realtime Research)")
    parser.add_argument("--problem", help="Nội dung bài toán")
    parser.add_argument("--problem_file", help="Đường dẫn tệp chứa bài toán")
    parser.add_argument("--output_file", help="Ghi lời giải ra tệp (tùy chọn)")
    parser.add_argument("--no_research", action="store_true", help="Tắt web research (Serper)")
    args = parser.parse_args()

    problem_text = args.problem or ""
    if args.problem_file and not problem_text:
        with open(args.problem_file, "r", encoding="utf-8") as f:
            problem_text = f.read()

    if not problem_text.strip():
        raise SystemExit("Vui lòng truyền --problem hoặc --problem_file")

    compiled = build_graph().compile()
    init_state = MathAgentState(problem_text=problem_text, use_research=(not args.no_research))
    final_state = await compiled.ainvoke(init_state)

    # LangGraph may return a plain dict; convert to state model if needed
    if isinstance(final_state, dict):
        final_state = MathAgentState(**final_state)

    # write with optional output path
    await write_solution(final_state, output_file=args.output_file)


if __name__ == "__main__":
    asyncio.run(main())


