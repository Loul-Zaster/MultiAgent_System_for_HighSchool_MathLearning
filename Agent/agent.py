import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import asyncio
from typing import Dict, Any, List
import google.generativeai as genai
from langgraph.graph import StateGraph, END
from typing import Annotated
from pydantic import BaseModel
from MCP.notion_mcp_client import NotionMCPClient
from MCP.markdown_converter import MarkdownConverter
from itertools import cycle
from dotenv import load_dotenv
import re

load_dotenv()

api_keys = []
i = 1
while key := os.getenv(f"GOOGLE_API_KEY_{i}"):
    api_keys.append(key)
    i += 1

NOTION_TOKEN = os.getenv("NOTION_TOKEN")

api_key_cycle = cycle(api_keys)
current_key = next(api_key_cycle)
genai.configure(api_key=current_key)

# STATE MODEL 
class AgentState(BaseModel):
    page_id: Annotated[str, "static"]
    problem_text: str = ""
    solution_text: str = ""

async def clean_marker(state: AgentState) -> AgentState:
    """
    Clean markdown formatting markers (*, **, ###) from LLM output.
    """
    if not state.solution_text:
        return state

    text = state.solution_text
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"^[\*\-]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)

    state.solution_text = text.strip()
    print("Solution after cleaning:\n", state.solution_text)
    return state

# STEPS / NODES 
async def read_problem(state: AgentState, notion: NotionMCPClient) -> AgentState:
    """Extract problem from Notion page"""
    page_id = state.page_id
    problem_texts: List[str] = []

    try:
        blocks_resp = await notion.client.get(
            f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
        )
        blocks_resp.raise_for_status()
        blocks_data = blocks_resp.json()

        for block in blocks_data.get("results", []):
            btype = block.get("type")
            bcontent = block.get(btype, {}) or {}
            if "rich_text" in bcontent:
                text = "".join(rt.get("plain_text", "") for rt in bcontent["rich_text"])
                if text.strip():
                    problem_texts.append(text)
            elif btype == "equation":
                expr = bcontent.get("expression", "")
                problem_texts.append(f"Equation: {expr}")
    except Exception as e:
        raise RuntimeError(f"Lỗi đọc nội dung: {e}")

    state.problem_text = "\n".join(problem_texts)
    print("Problem extracted:\n", state.problem_text)
    return state

async def solve_problem(state: AgentState) -> AgentState:
    if not state.problem_text.strip():
        raise ValueError("Không có nội dung toán để giải")
    
    prompt = f"Hãy giải chi tiết bài toán sau (bằng LaTeX nếu cần):\n{state.problem_text}"

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = await asyncio.to_thread(model.generate_content, prompt)

    state.solution_text = response.text
    return state

async def write_solution(state: AgentState, notion: NotionMCPClient) -> AgentState:
    """Append solution to Notion page"""
    if not state.solution_text:
        raise ValueError("Không có lời giải để ghi")

    md_solution = f"Lời giải:\n{state.solution_text}"
    await notion.update_page(state.page_id, content=md_solution)

    print("Solution written back to Notion page")
    return state

#  GRAPH ASSEMBLY 
def build_graph(notion: NotionMCPClient):
    graph = StateGraph(AgentState)

    # add nodes
    async def read_problem_node(state):
        return await read_problem(state, notion)

    async def solve_problem_node(state):
        return await solve_problem(state)

    async def clean_marker_node(state):
        return await clean_marker(state)

    async def write_solution_node(state):
        return await write_solution(state, notion)

    graph.add_node("read_problem", read_problem_node)
    graph.add_node("solve_problem", solve_problem_node)
    graph.add_node("clean_marker", clean_marker_node)
    graph.add_node("write_solution", write_solution_node)

    # edges: read -> solve -> write -> END
    graph.add_edge("read_problem", "solve_problem")
    graph.add_edge("solve_problem", "clean_marker")
    graph.add_edge("clean_marker", "write_solution")
    graph.add_edge("write_solution", END)

    graph.set_entry_point("read_problem")
    return graph

async def run_agent(page_id: str):
    notion_client = NotionMCPClient("mcp_server.py", NOTION_TOKEN)
    async with notion_client.connect():
        graph = build_graph(notion_client).compile()
        init_state = AgentState(page_id=page_id)
        result_state = await graph.ainvoke(init_state)
        return result_state

#  RUN MAIN 
async def main():
    import argparse

    parser = argparse.ArgumentParser()
    default_server = os.path.abspath("/teamspace/studios/this_studio/MCP/mcp_server.py")
    parser.add_argument("--server", default=default_server, help="MCP server command")
    parser.add_argument("--page", required=True, help="26974e97-008f-80ac-b77d-dbc6a7fe7726")
    args = parser.parse_args()

    notion_client = NotionMCPClient(args.server, NOTION_TOKEN)

    async with notion_client.connect():
        graph = build_graph(notion_client).compile()

        init_state = AgentState(page_id=args.page)
        result_state = await graph.ainvoke(init_state)

        print("Problem:", result_state["problem_text"])
        print("Solution:", result_state["solution_text"])

if __name__ == "__main__":
    asyncio.run(main())