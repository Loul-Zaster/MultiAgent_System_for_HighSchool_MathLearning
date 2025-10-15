import os
import asyncio
from typing import List, Dict, Any

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from pydantic import BaseModel
from groq import Groq

import aiohttp
from bs4 import BeautifulSoup


load_dotenv()


# ========== Configuration ==========
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client: Groq | None = None
try:
    groq_client = Groq()
except Exception:
    groq_client = None


# ========== State Model ==========
class ResearchAgentState(BaseModel):
    question: str
    research_results: List[Dict[str, str]] = []
    compiled_context: str = ""
    answer: str = ""


# ========== Research Tool ==========
async def ddg_search(query: str, max_results: int = 5, timeout_seconds: int = 12) -> List[Dict[str, str]]:
    """Perform a lightweight DuckDuckGo HTML search and extract top results.

    Returns a list of {title, url, snippet}.
    """
    # DuckDuckGo's lightweight HTML endpoint is simple to parse and works without JS
    search_url = "https://html.duckduckgo.com/html/"
    params = {"q": query}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.post(search_url, data=params, timeout=timeout_seconds) as resp:
                html = await resp.text()
        except Exception:
            return []

    soup = BeautifulSoup(html, "html.parser")
    results: List[Dict[str, str]] = []

    # DuckDuckGo HTML layout: results are within "result" containers
    for result in soup.select(".result"):
        link_el = result.select_one("a.result__a")
        snippet_el = result.select_one(".result__snippet") or result.select_one(".result__snippet.js-result-snippet")
        if not link_el:
            continue
        title = link_el.get_text(" ", strip=True)
        url = link_el.get("href", "")
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
        if title and url:
            results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= max_results:
            break

    return results


async def build_compiled_context(results: List[Dict[str, str]], max_chars: int = 1800) -> str:
    """Compile search results into a concise context string for the LLM."""
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


# ========== Graph Nodes ==========
async def research_node(state: ResearchAgentState) -> ResearchAgentState:
    if not state.question.strip():
        raise ValueError("Question is empty.")

    results = await ddg_search(state.question, max_results=6)
    state.research_results = results
    state.compiled_context = await build_compiled_context(results)
    print("Research results found:", len(results))
    return state


async def solve_node(state: ResearchAgentState) -> ResearchAgentState:
    if groq_client is None:
        # Fallback if Groq client is not available/configured
        context_section = f"\n\nSources:\n{state.compiled_context}" if state.compiled_context else ""
        state.answer = (
            "(GROQ not configured) Here's a synthesized answer based on search results.\n\n"
            f"Question: {state.question}\n" + context_section
        )
        return state

    system_prompt = (
        "You are a precise research assistant. Use the provided web findings to answer the question.\n"
        "- Cite sources inline with [n] where n is the result index when a claim relies on a source.\n"
        "- If information is uncertain or conflicting, state that clearly.\n"
        "- Keep the answer concise and actionable."
    )
    user_prompt = (
        f"Question:\n{state.question}\n\n"
        f"Web findings (indexed):\n{state.compiled_context}\n\n"
        "Answer:"
    )

    accumulated: List[str] = []
    try:
        completion = groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_completion_tokens=1024,
            top_p=1,
            reasoning_effort="medium",
            stream=True,
            stop=None,
        )

        # Stream and accumulate
        for chunk in completion:
            delta = getattr(chunk.choices[0], "delta", None)
            if delta and getattr(delta, "content", None):
                text_part = delta.content
                accumulated.append(text_part)
        state.answer = "".join(accumulated)
    except Exception as e:
        state.answer = f"(GROQ error) {e}\n\nQuestion: {state.question}\n\nSources:\n{state.compiled_context}"

    return state


async def output_node(state: ResearchAgentState) -> ResearchAgentState:
    print("\n=== Answer ===\n")
    print(state.answer)
    if state.research_results:
        print("\n=== Sources ===")
        for idx, item in enumerate(state.research_results, start=1):
            print(f"[{idx}] {item.get('title','')} - {item.get('url','')}")
    return state


# ========== Graph Assembly ==========
def build_graph():
    graph = StateGraph(ResearchAgentState)

    async def research_node_wrapper(state):
        return await research_node(state)

    async def solve_node_wrapper(state):
        return await solve_node(state)

    async def output_node_wrapper(state):
        return await output_node(state)

    graph.add_node("research", research_node_wrapper)
    graph.add_node("solve", solve_node_wrapper)
    graph.add_node("output", output_node_wrapper)

    graph.add_edge("research", "solve")
    graph.add_edge("solve", "output")
    graph.add_edge("output", END)

    graph.set_entry_point("research")
    return graph


# ========== CLI ==========
async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Standalone LangGraph research agent")
    parser.add_argument("--question", required=True, help="User question to research and answer")
    args = parser.parse_args()

    compiled_graph = build_graph().compile()
    init_state = ResearchAgentState(question=args.question)
    final_state = await compiled_graph.ainvoke(init_state)

    # For programmatic usage, you could return final_state here
    return final_state


if __name__ == "__main__":
    asyncio.run(main())


