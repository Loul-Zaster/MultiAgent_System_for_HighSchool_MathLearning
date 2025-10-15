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
        print("🧠 Solution (fallback) ready")
        return state

    system_prompt = (
        "Bạn là trợ lý giải toán chi tiết và chính xác.\n"
        "- Diễn giải từng bước ngắn gọn, kèm ký hiệu LaTeX khi cần.\n"
        "- Nếu có nguồn/công thức từ web research, trích dẫn [n].\n"
        "- Nêu giả thiết, kết luận rõ ràng."
    )
    user_prompt = (
        f"Bài toán:\n{state.problem_text}\n\n"
        f"Web findings (indexed):\n{state.compiled_context}\n\n"
        "Lời giải chi tiết:"
    )

    parts: List[str] = []
    try:
        completion = groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_completion_tokens=2048,
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
        print("🧠 Solution generated")
    except Exception as e:
        state.solution_text = f"(GROQ error) {e}"
    return state


async def write_solution(state: MathAgentState, output_file: Optional[str] = None) -> MathAgentState:
    if not state.solution_text or not state.solution_text.strip():
        print("⚠️ Không có lời giải để ghi")
        return state
    
    header = "### Lời giải:\n"
    content = header + state.solution_text
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"💾 Solution written to {output_file}")
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


