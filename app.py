import os
import sys
import subprocess
import asyncio
import streamlit as st
from MCP.notion_mcp_client import NotionMCPClient
sys.path.append(os.path.join(os.path.dirname(__file__), "MCP"))
sys.path.append(os.path.join(os.path.dirname(__file__)))

import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()

# Import Master Agent
from Agent.master_agent import build_master_graph, MasterAgentState

api_key = os.getenv("GOOGLE_API_KEY_1")
if not api_key:
    st.error("Thiếu GOOGLE_API_KEY_1 trong .env")
else:
    genai.configure(api_key=api_key)

# Streamlit Page Setup
st.set_page_config(page_title="DS445 Assistant", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS for professional chat interface
st.markdown("""
<style>
    /* Global styles */
    * {
        box-sizing: border-box;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Main container - full width */
    .main .block-container {
        padding: 0;
        max-width: 100%;
        margin: 0;
    }
    
    /* Remove default Streamlit padding */
    .stApp {
        margin: 0;
        padding: 0;
    }
    
    /* Main layout container */
    .chat-layout {
        display: flex;
        height: 100vh;
        overflow: hidden;
        background-color: #f5f5f5;
    }
    
    /* Sidebar panels */
    .sidebar-panel {
        width: 320px;
        background: white;
        border-right: 1px solid #e0e0e0;
        overflow-y: auto;
        transition: transform 0.3s ease;
        box-shadow: 2px 0 8px rgba(0,0,0,0.05);
    }
    
    .sidebar-panel.hidden {
        transform: translateX(-100%);
        width: 0;
    }
    
    .right-panel {
        border-right: none;
        border-left: 1px solid #e0e0e0;
        box-shadow: -2px 0 8px rgba(0,0,0,0.05);
    }
    
    .right-panel.hidden {
        transform: translateX(100%);
        width: 0;
    }
    
    /* Chat main area */
    .chat-main {
        flex: 1;
        display: flex;
        flex-direction: column;
        background: white;
        position: relative;
    }
    
    /* Top bar */
    .top-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1rem 1.5rem;
        background: white;
        border-bottom: 1px solid #e0e0e0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        z-index: 10;
    }
    
    .top-bar h1 {
        margin: 0;
        font-size: 1.5rem;
        font-weight: 600;
        color: #1a1a1a;
    }
    
    /* Toggle buttons */
    .toggle-btn {
        background: #f8f9fa;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        cursor: pointer;
        font-size: 0.9rem;
        color: #495057;
        transition: all 0.2s;
    }
    
    .toggle-btn:hover {
        background: #e9ecef;
        border-color: #dee2e6;
    }
    
    /* Chat messages area */
    .chat-messages-container {
        flex: 1;
        overflow-y: auto;
        padding: 2rem;
        background: linear-gradient(to bottom, #fafafa 0%, #ffffff 100%);
    }
    
    /* Chat message styling */
    .stChatMessage {
        background: white;
        border-radius: 16px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border: 1px solid #e8e8e8;
        position: relative;
        overflow: hidden;
    }
    
    /* User message */
    [data-testid="stChatMessage"][data-role="user"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-color: #667eea;
        color: white;
        margin-left: 20%;
    }
    
    [data-testid="stChatMessage"][data-role="user"] .stMarkdown {
        color: white;
    }
    
    [data-testid="stChatMessage"][data-role="user"] .stMarkdown h1,
    [data-testid="stChatMessage"][data-role="user"] .stMarkdown h2,
    [data-testid="stChatMessage"][data-role="user"] .stMarkdown h3,
    [data-testid="stChatMessage"][data-role="user"] .stMarkdown h4,
    [data-testid="stChatMessage"][data-role="user"] .stMarkdown h5,
    [data-testid="stChatMessage"][data-role="user"] .stMarkdown h6 {
        color: white;
    }
    
    /* Assistant message */
    [data-testid="stChatMessage"][data-role="assistant"] {
        background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
        border-color: #e9ecef;
        margin-right: 20%;
    }
    
    /* Chat message avatar */
    [data-testid="stChatMessage"] .stChatMessage__avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.2rem;
        font-weight: bold;
    }
    
    [data-testid="stChatMessage"][data-role="user"] .stChatMessage__avatar {
        background: rgba(255,255,255,0.2);
        color: white;
    }
    
    [data-testid="stChatMessage"][data-role="assistant"] .stChatMessage__avatar {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    
    /* Chat input area */
    .chat-input-container {
        padding: 1.5rem;
        background: white;
        border-top: 1px solid #e0e0e0;
        box-shadow: 0 -2px 8px rgba(0,0,0,0.05);
    }
    
    /* Streamlit chat input */
    .stChatInput textarea {
        border: 2px solid #e0e0e0 !important;
        border-radius: 12px !important;
        padding: 1rem !important;
        font-size: 0.95rem !important;
        resize: none !important;
    }
    
    .stChatInput textarea:focus {
        border-color: #2196F3 !important;
        box-shadow: 0 0 0 3px rgba(33, 150, 243, 0.1) !important;
    }
    
    /* (attachment button styles removed; using a separate column button) */
    
    /* Button styling */
    .stButton > button {
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        padding: 0.5rem 1rem;
        font-weight: 500;
        transition: all 0.2s;
        background: white;
        color: #495057;
    }
    
    .stButton > button:hover {
        background: #f8f9fa;
        border-color: #dee2e6;
        transform: translateY(-1px);
    }
    
    .stButton > button[kind="primary"] {
        background: #2196F3;
        color: white;
        border-color: #2196F3;
    }
    
    .stButton > button[kind="primary"]:hover {
        background: #1976D2;
        border-color: #1976D2;
    }
    
    /* Status badge */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.4rem 0.8rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 500;
    }
    
    .status-running {
        background: #e8f5e9;
        color: #2e7d32;
    }
    
    .status-stopped {
        background: #ffebee;
        color: #c62828;
    }
    
    .status-active {
        background: #e3f2fd;
        color: #1565c0;
    }
    
    .status-info {
        background: #f5f5f5;
        color: #616161;
    }
    
    /* Section headers */
    .section-header {
        font-size: 1rem;
        font-weight: 600;
        color: #1a1a1a;
        margin: 1.5rem 0 1rem 0;
        padding: 0 1rem;
    }
    
    /* Content padding */
    .panel-content {
        padding: 1rem;
    }
    
    /* Input fields */
    .stTextInput input {
        border: 1px solid #e0e0e0 !important;
        border-radius: 8px !important;
        padding: 0.6rem !important;
    }
    
    .stTextInput input:focus {
        border-color: #2196F3 !important;
        box-shadow: 0 0 0 2px rgba(33, 150, 243, 0.1) !important;
    }
    
    /* File uploader */
    .stFileUploader {
        border: 2px dashed #e0e0e0;
        border-radius: 12px;
        padding: 1.5rem;
        background: #fafafa;
    }
    
    .stFileUploader:hover {
        border-color: #2196F3;
        background: #f5f9ff;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background: #f8f9fa;
        border-radius: 8px;
        font-weight: 500;
        border: 1px solid #e9ecef;
    }
    
    /* Metrics */
    [data-testid="stMetricValue"] {
        font-size: 1.5rem;
        font-weight: 600;
        color: #1a1a1a;
    }
    
    [data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        color: #757575;
    }
    
    /* Divider */
    hr {
        margin: 1rem 0;
        border: none;
        border-top: 1px solid #e9ecef;
    }
    
    /* Scrollbar */
    .chat-messages-container::-webkit-scrollbar,
    .sidebar-panel::-webkit-scrollbar {
        width: 6px;
    }
    
    .chat-messages-container::-webkit-scrollbar-track,
    .sidebar-panel::-webkit-scrollbar-track {
        background: #f5f5f5;
    }
    
    .chat-messages-container::-webkit-scrollbar-thumb,
    .sidebar-panel::-webkit-scrollbar-thumb {
        background: #bdbdbd;
        border-radius: 3px;
    }
    
    .chat-messages-container::-webkit-scrollbar-thumb:hover,
    .sidebar-panel::-webkit-scrollbar-thumb:hover {
        background: #9e9e9e;
    }
    
    /* Empty state */
    .empty-state {
        text-align: center;
        padding: 4rem 2rem;
        color: #757575;
    }
    
    .empty-state-icon {
        font-size: 4rem;
        margin-bottom: 1rem;
        opacity: 0.5;
    }
    
    .empty-state h3 {
        color: #424242;
        font-weight: 500;
        margin-bottom: 0.5rem;
    }
    
    /* OCR Section */
    .ocr-section {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        border: 1px solid #e9ecef;
    }
    
    .ocr-title {
        font-size: 0.95rem;
        font-weight: 600;
        color: #495057;
        margin-bottom: 0.75rem;
    }
    
    /* Code blocks */
    code {
        background: #f5f5f5;
        padding: 0.2rem 0.4rem;
        border-radius: 4px;
        font-size: 0.9rem;
    }
    
    /* Info boxes */
    .info-box {
        background: #f8f9fa;
        border-left: 3px solid #2196F3;
        padding: 0.75rem 1rem;
        border-radius: 4px;
        margin: 0.5rem 0;
        font-size: 0.9rem;
        color: #495057;
    }
</style>
""", unsafe_allow_html=True)

project_root = os.path.abspath(os.getcwd())
server_path = os.path.abspath(os.path.join(project_root, "MCP", "mcp_server.py"))
main_py = os.path.abspath(os.path.join(project_root, "MCP", "main.py"))

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
if not NOTION_TOKEN:
    st.error("Thiếu NOTION_TOKEN trong .env hoặc môi trường")
    st.stop()

# MCP Server management
def ensure_mcp_server():
    if not os.path.exists(server_path):
        st.session_state["mcp_status"] = "missing"
        return

    proc = st.session_state.get("mcp_proc")
    if proc is not None and proc.poll() is None:
        st.session_state["mcp_status"] = "running"
        return

    try:
        proc = subprocess.Popen(
            [
                sys.executable, main_py,
                "--server", server_path,
                "--token", NOTION_TOKEN,
                "--interactive"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        st.session_state["mcp_proc"] = proc
        st.session_state["mcp_status"] = "running"
    except Exception as e:
        st.session_state["mcp_status"] = f"error: {e}"

def stop_mcp_server():
    proc = st.session_state.get("mcp_proc")
    if proc and proc.poll() is None:
        proc.terminate()
    st.session_state["mcp_status"] = "stopped"

if "mcp_bootstrapped" not in st.session_state:
    ensure_mcp_server()
    st.session_state["mcp_bootstrapped"] = True

# Init States
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "ocr_last_text" not in st.session_state:
    st.session_state["ocr_last_text"] = ""
if "notion_page_id" not in st.session_state:
    st.session_state["notion_page_id"] = ""
if "notion_problem" not in st.session_state:
    st.session_state["notion_problem"] = ""
if "notion_problems" not in st.session_state:
    st.session_state["notion_problems"] = {}
if "selected_problem" not in st.session_state:
    st.session_state["selected_problem"] = None
if "master_agent_context" not in st.session_state:
    st.session_state["master_agent_context"] = ""
if "master_agent_graph" not in st.session_state:
    st.session_state["master_agent_graph"] = build_master_graph().compile()
if "show_left_panel" not in st.session_state:
    st.session_state["show_left_panel"] = False
if "show_right_panel" not in st.session_state:
    st.session_state["show_right_panel"] = True

# Functions
async def fetch_problem(page_id: str) -> dict:
    """Fetch and parse problems from Notion page"""
    notion = NotionMCPClient(server_path, NOTION_TOKEN)
    async with notion.connect():
        blocks_resp = await notion.client.get(
            f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
        )
        blocks_resp.raise_for_status()
        blocks_data = blocks_resp.json()
        
        # Parse all text blocks
        all_text = []
        for block in blocks_data.get("results", []):
            btype = block.get("type")
            bcontent = block.get(btype, {}) or {}
            if "rich_text" in bcontent:
                text = "".join(rt.get("plain_text", "") for rt in bcontent["rich_text"])
                if text.strip():
                    all_text.append(text)
        
        full_content = "\n".join(all_text)
        
        # Try to split by "Bài" or "Problem" markers
        import re
        problems = {}
        
        # Pattern: Bài 1, Bài số 1, Problem 1, etc.
        pattern = r'(?:Bài|Problem)\s*(?:số\s*)?(\d+)'
        matches = list(re.finditer(pattern, full_content, re.IGNORECASE))
        
        if matches:
            for i, match in enumerate(matches):
                problem_num = match.group(1)
                start_idx = match.start()
                end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(full_content)
                
                problem_content = full_content[start_idx:end_idx].strip()
                problems[f"Bài {problem_num}"] = problem_content
        else:
            # If no markers found, treat as single problem
            problems["Toàn bộ"] = full_content
        
        return {
            "full_content": full_content,
            "problems": problems
        }

async def append_markdown_to_notion(page_id: str, content: str, mode: str = "add") -> str:
    """Append or replace markdown content on a Notion page via MCP.
    mode: "add" to append blocks, "edit" to replace all blocks.
    Returns server message.
    """
    ensure_mcp_server()
    client = NotionMCPClient(server_path, NOTION_TOKEN)
    async with client.connect():
        return await client.update_page(page_id=page_id, content=content, mode=mode)

async def run_master_agent(prompt: str, context: str = "") -> str:
    try:
        master_graph = st.session_state["master_agent_graph"]
        
        # Build context with selected problem info
        full_context = context
        if st.session_state.get("selected_problem"):
            selected = st.session_state["selected_problem"]
            problem_content = st.session_state["notion_problems"].get(selected, "")
            # Only use Notion context if user explicitly references the selected problem
            if any(keyword in prompt.lower() for keyword in [f"bài số {selected.split()[-1]}", f"bài {selected.split()[-1]}", selected.lower()]):
                full_context = f"{selected}\n\n{problem_content}"
            else:
                # For other math problems, don't use Notion context
                full_context = context
        
        init_state = MasterAgentState(
            user_prompt=prompt,
            short_term_context=full_context,
            long_term_context=st.session_state.get("master_agent_context", "")
        )
        
        result_state = await master_graph.ainvoke(init_state)
        
        if isinstance(result_state, dict):
            return result_state.get('result', 'Không có kết quả')
        else:
            return result_state.result if hasattr(result_state, 'result') else str(result_state)
            
    except Exception as e:
        return f"Lỗi Master Agent: {e}"

def render_latex_content(content: str) -> str:
    """Clean LaTeX content for proper rendering"""
    import re
    
    # Fix broken LaTeX patterns from the image - be more careful with regex
    try:
        # Fix broken LaTeX commands by removing extra asterisks
        content = re.sub(r'\\frac\{([^}]*)\*\*\{([^}]*)\*\*\}', r'\\frac{\1}{\2}', content)
        content = re.sub(r'\\binom\{([^}]*)\*\*\{([^}]*)\*\*\}', r'\\binom{\1}{\2}', content)
        content = re.sub(r'\\sum_\{([^}]*)\*\*}', r'\\sum_{\1}', content)
        
        # Fix broken aligned environment
        content = re.sub(r'\\begin\{aligned\*\*}', r'\\begin{aligned}', content)
        content = re.sub(r'\\end\{aligned\*\*}', r'\\end{aligned}', content)
        
        # Fix bold markers carefully
        content = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', content)
        
    except Exception as e:
        # If regex fails, just return the content as-is
        pass
    
    # Ensure proper LaTeX delimiters
    content = content.replace('\\[', '$$').replace('\\]', '$$')
    content = content.replace('\\(', '$').replace('\\)', '$')
    
    return content

# Add KaTeX for LaTeX rendering
st.markdown("""
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css" integrity="sha384-GvrOXuhMATgEsSwCs4smul74iXGOixntILdUW9XmUC6+HX0sLNAK3q71HotJqlAn" crossorigin="anonymous">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js" integrity="sha384-cpW21h6RZv/phavutF+AuVYrr+dA8xD9zs6FwLpaCct6O9ctzYFfFr4dgmgccOTx" crossorigin="anonymous"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js" integrity="sha384-+VBxd3r6XgURycqtZ117nYw44OOcIax56Z4dCRWbxyPt0Koah1uHoK0o4+/RRE05" crossorigin="anonymous"></script>
<script>
document.addEventListener("DOMContentLoaded", function() {
    renderMathInElement(document.body, {
        delimiters: [
            {left: '$$', right: '$$', display: true},
            {left: '$', right: '$', display: false},
            {left: '\\[', right: '\\]', display: true},
            {left: '\\(', right: '\\)', display: false}
        ],
        throwOnError: false
    });
});
</script>
""", unsafe_allow_html=True)

# Top navigation bar
col1, col2 = st.columns([1, 4])

with col1:
    if st.button("☰ Cài đặt" if not st.session_state["show_left_panel"] else "✕ Đóng", key="toggle_left"):
        st.session_state["show_left_panel"] = not st.session_state["show_left_panel"]
        st.rerun()

with col2:
    st.markdown("<h1 style='text-align: left; margin: 0;'>💬 MULTI-AGENT HỖ TRỢ HỌC TOÁN THPT</h1>", unsafe_allow_html=True)

st.divider()

# Main layout with 3 columns - Right panel always visible
if st.session_state["show_left_panel"]:
    left, center, right = st.columns([1, 2.5, 1])
else:
    center, right = st.columns([3.5, 1])
    left = None

# LEFT PANEL - Settings
if st.session_state["show_left_panel"] and left is not None:
    with left:
        st.markdown('<div class="panel-content">', unsafe_allow_html=True)
        
        st.markdown("### 🔌 MCP Status")
        status = st.session_state.get("mcp_status", "unknown")
        
        if status == "running":
            st.markdown('<div class="status-badge status-running">🟢 Đang chạy</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-badge status-stopped">🔴 Dừng</div>', unsafe_allow_html=True)
        
        st.caption(f"Server: {os.path.basename(server_path)}")
        
        col1, col2 = st.columns(2)
        with col1:
            if status == "running":
                if st.button("Ngắt", use_container_width=True, key="stop_mcp"):
                    stop_mcp_server()
                    st.rerun()
            else:
                if st.button("Kết nối", use_container_width=True, type="primary", key="start_mcp"):
                    ensure_mcp_server()
                    st.rerun()
        with col2:
            if st.button("Refresh", use_container_width=True, key="refresh_mcp"):
                st.rerun()
        
        st.divider()
        
        # Notion Section with better styling
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 1rem; border-radius: 12px; margin-bottom: 1rem;">
            <h3 style="color: white; margin: 0; font-size: 1.1rem;">📑 Notion Integration</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Page ID input with better styling
        st.markdown("**Page ID:**")
        page_id = st.text_input(
            "Notion Page ID", 
            value=st.session_state["notion_page_id"],
            key="notion_page",
            placeholder="Nhập Notion page ID...",
            label_visibility="collapsed"
        )
        
        # Read button with better styling
        if st.button("📥 Đọc bài toán từ Notion", use_container_width=True, disabled=not page_id, type="primary"):
            try:
                with st.spinner("🔄 Đang đọc từ Notion..."):
                    result = asyncio.run(fetch_problem(page_id))
                    st.session_state["notion_page_id"] = page_id
                    st.session_state["notion_problem"] = result["full_content"]
                    st.session_state["notion_problems"] = result["problems"]
                    
                    num_problems = len(result["problems"])
                    st.success(f"✅ Đã tìm thấy {num_problems} bài toán từ Notion")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Lỗi khi đọc Notion: {e}")
        
        # Display problem selector with better styling
        if st.session_state["notion_problems"]:
            st.markdown("---")
            st.markdown("""
            <div style="background: #f8f9fa; padding: 0.75rem; border-radius: 8px; margin-bottom: 1rem;">
                <h4 style="margin: 0; color: #495057;">📚 Chọn bài toán:</h4>
            </div>
            """, unsafe_allow_html=True)
            
            problem_keys = list(st.session_state["notion_problems"].keys())
            
            for i, key in enumerate(problem_keys):
                # Create a card-like container for each problem
                st.markdown(f"""
                <div style="background: white; border: 1px solid #e9ecef; border-radius: 8px; 
                            padding: 0.75rem; margin-bottom: 0.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 500; color: #495057;">{key}</span>
                        <span style="font-size: 0.8rem; color: #6c757d;">Bài {i+1}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns([4, 1])
                with col1:
                    if st.button(f"📖 Xem chi tiết", key=f"view_{key}", use_container_width=True):
                        with st.expander(f"📄 Chi tiết {key}", expanded=True):
                            content = st.session_state["notion_problems"][key]
                            st.markdown(f"```\n{content}\n```")
                
                with col2:
                    if st.button("✓", key=f"select_{key}", use_container_width=True, type="primary"):
                        st.session_state["selected_problem"] = key
                        problem_content = st.session_state["notion_problems"][key]
                        st.session_state["master_agent_context"] = f"Đang xử lý {key}:\n\n{problem_content}"
                        
                        # Add to chat with better formatting
                        st.session_state["messages"].append({
                            "role": "user", 
                            "content": f"📚 **{key}**\n\n{problem_content}"
                        })
                        st.success(f"✅ Đã chọn {key} và thêm vào chat")
                        st.rerun()
            
            st.markdown("---")
            
            # Show selected problem with better styling
            if st.session_state["selected_problem"]:
                st.markdown("""
                <div style="background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); 
                            padding: 1rem; border-radius: 8px; border-left: 4px solid #4caf50;">
                    <h4 style="margin: 0; color: #2e7d32;">📌 Bài toán đã chọn</h4>
                </div>
                """, unsafe_allow_html=True)
                
                with st.expander(f"📄 {st.session_state['selected_problem']}", expanded=True):
                    content = st.session_state["notion_problems"][st.session_state["selected_problem"]]
                    st.markdown(f"```\n{content}\n```")
        
        elif st.session_state["notion_problem"]:
            st.markdown("---")
            st.markdown("""
            <div style="background: #f8f9fa; padding: 0.75rem; border-radius: 8px;">
                <h4 style="margin: 0; color: #495057;">📄 Nội dung từ Notion</h4>
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander("📄 Xem nội dung", expanded=False):
                st.markdown(f"```\n{st.session_state['notion_problem']}\n```")
        
        st.markdown('</div>', unsafe_allow_html=True)

# CENTER PANEL - Main Chat
with center:
    # Chat messages
    if len(st.session_state["messages"]) == 0:
        st.markdown("""
        <div style="text-align: center; padding: 4rem 2rem; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); 
                    border-radius: 16px; margin: 2rem 0;">
            <div style="font-size: 4rem; margin-bottom: 1rem;">🤖</div>
            <h3 style="color: #2c3e50; font-weight: 600; margin-bottom: 0.5rem;">Chào mừng đến với Hệ thống Multi-Agent hỗ trợ học Toán THPT!</h3>
            <p style="color: #7f8c8d; font-size: 1.1rem; margin-bottom: 2rem;">Tôi có thể giúp bạn giải toán, nghiên cứu, và trả lời các câu hỏi</p>
            <div style="display: flex; justify-content: center; gap: 1rem; flex-wrap: wrap;">
                <div style="background: white; padding: 1rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); min-width: 200px;">
                    <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">🧮</div>
                    <div style="font-weight: 500; color: #2c3e50;">Giải toán</div>
                    <div style="font-size: 0.9rem; color: #7f8c8d;">Giải các bài toán từ cơ bản đến nâng cao</div>
                </div>
                <div style="background: white; padding: 1rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); min-width: 200px;">
                    <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">🔍</div>
                    <div style="font-weight: 500; color: #2c3e50;">Nghiên cứu</div>
                    <div style="font-size: 0.9rem; color: #7f8c8d;">Tìm kiếm và phân tích thông tin</div>
                </div>
                <div style="background: white; padding: 1rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); min-width: 200px;">
                    <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">📝</div>
                    <div style="font-weight: 500; color: #2c3e50;">OCR</div>
                    <div style="font-size: 0.9rem; color: #7f8c8d;">Trích xuất văn bản từ ảnh</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for m in st.session_state["messages"]:
            with st.chat_message(m["role"]):
                rendered_content = render_latex_content(m["content"])
                st.markdown(rendered_content)
    
    # # OCR Section with better styling
    # st.markdown("""
    # <div style="background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%); 
    #             padding: 1rem; border-radius: 12px; margin-bottom: 1rem;">
    #     <h3 style="color: #8b4513; margin: 0; font-size: 1.1rem;">🖼️ OCR - Trích xuất văn bản từ ảnh</h3>
    # </div>
    # """, unsafe_allow_html=True)
    
    # ocr_col1, ocr_col2 = st.columns([3, 1])
    # with ocr_col1:
    #     uploaded = st.file_uploader(
    #         "Chọn ảnh để trích xuất văn bản", 
    #         type=["png", "jpg", "jpeg"], 
    #         key="ocr_uploader",
    #         label_visibility="collapsed",
    #         help="Hỗ trợ định dạng PNG, JPG, JPEG"
    #     )
    # with ocr_col2:
    #     if st.button("📤 Trích xuất văn bản", disabled=(uploaded is None), use_container_width=True, type="primary"):
    #         if uploaded:
    #             try:
    #                 from ocr_model import run_ocr
    #                 text = run_ocr(uploaded.getvalue())
    #                 st.session_state["ocr_last_text"] = text
    #                 st.session_state["messages"].append({"role": "user", "content": text})
                    
    #                 # Show user message immediately
    #                 with st.chat_message("user"):
    #                     rendered_text = render_latex_content(text)
    #                     st.markdown(rendered_text)
                    
    #                 # Show thinking indicator in chat area
    #                 with st.chat_message("assistant"):
    #                     with st.spinner("🤔 Đang suy nghĩ..."):
    #                         reply = asyncio.run(run_master_agent(text))
                    
    #                 # Add assistant response to messages
    #                 st.session_state["messages"].append({"role": "assistant", "content": reply})
                    
    #                 # Show assistant response
    #                 with st.chat_message("assistant"):
    #                     rendered_reply = render_latex_content(reply)
    #                     st.markdown(rendered_reply)
                    
    #                 st.rerun()
    #             except Exception as e:
    #                 st.error(f"❌ Lỗi: {e}")
    
    # Chat input with auto-resize
    st.markdown("""
    <style>
    .stChatInput > div > div > div > div > div {
        min-height: 40px !important;
        max-height: 200px !important;
        overflow-y: auto !important;
    }
    /* Ensure any previously injected attach button is hidden */
    .attach-btn { display: none !important; }
    .stChatInput textarea {
        resize: none !important;
        min-height: 40px !important;
        max-height: 200px !important;
        height: auto !important;
    }
    </style>
    
    <script>
    function autoResizeTextarea() {
        const textareas = document.querySelectorAll('.stChatInput textarea');
        textareas.forEach(textarea => {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
        });
    }
    
    // Auto-resize on input
    document.addEventListener('input', function(e) {
        if (e.target.tagName === 'TEXTAREA' && e.target.closest('.stChatInput')) {
            autoResizeTextarea();
        }
    });
    
    // Auto-resize on page load
    document.addEventListener('DOMContentLoaded', autoResizeTextarea);
    
    // Auto-resize after Streamlit updates
    setTimeout(() => { autoResizeTextarea(); }, 100);
    setTimeout(() => { autoResizeTextarea(); }, 500);
    </script>
    """, unsafe_allow_html=True)
    
    # Paperclip button next to chat input
    chat_left, chat_right = st.columns([0.08, 0.92])
    with chat_left:
        st.button("📎", key="attach_clip", help="Tệp đính kèm", use_container_width=True)
    with chat_right:
        prompt = st.chat_input("💭 Nhập tin nhắn của bạn...", key="main_chat_input")
    
    if prompt:
        st.session_state["messages"].append({"role": "user", "content": prompt})
        
        # Show user message immediately
        with st.chat_message("user"):
            rendered_prompt = render_latex_content(prompt)
            st.markdown(rendered_prompt)
        
        # Show thinking indicator in chat area
        with st.chat_message("assistant"):
            with st.spinner("🤔 Đang suy nghĩ..."):
                reply = asyncio.run(run_master_agent(prompt))
        
        # Add assistant response to messages
        st.session_state["messages"].append({"role": "assistant", "content": reply})

        # Optionally save to Notion via MCP if page id is available
        page_id = st.session_state.get("notion_page_id", "").strip()
        if page_id:
            try:
                # Build a simple markdown section for this exchange
                md = f"""
### 💬 Trao đổi

**Người dùng:**

{prompt}

**Trợ lý:**

{reply}
""".strip()
                status = asyncio.run(append_markdown_to_notion(page_id, md, mode="add"))
                st.toast("✅ Đã lưu vào Notion", icon="✅")
            except Exception as e:
                st.toast(f"⚠️ Không lưu được vào Notion: {e}", icon="⚠️")
        
        # Show assistant response
        with st.chat_message("assistant"):
            rendered_reply = render_latex_content(reply)
            st.markdown(rendered_reply)
        
        st.rerun()

# RIGHT PANEL - Info (always visible)
if right is not None:
    with right:
        st.markdown('<div class="panel-content">', unsafe_allow_html=True)
        
        st.markdown("### 🤖 Agent")
        
        if st.session_state.get("master_agent_context"):
            st.markdown('<div class="status-badge status-active">✅ Context đang hoạt động</div>', unsafe_allow_html=True)
            st.caption(f"{len(st.session_state['master_agent_context'])} ký tự")
        else:
            st.markdown('<div class="status-badge status-info">ℹ️ Không có context</div>', unsafe_allow_html=True)
        
        st.divider()
        
        st.markdown("### 🧠 Bộ nhớ")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Xóa", use_container_width=True):
                st.session_state["master_agent_context"] = ""
                st.session_state["messages"] = []
                st.rerun()
        with col2:
            if st.button("📊 Thống kê", use_container_width=True):
                try:
                    from Memory.long_term import LongTermMemoryManager
                    ltm = LongTermMemoryManager()
                    memories = ltm.list_all_memories(limit=10)
                    st.info(f"Tổng: {len(memories)}")
                except Exception as e:
                    st.error(f"Lỗi: {e}")
        
        st.divider()
        
        st.markdown("### 📊 Hệ thống")
        st.metric("Tin nhắn", len(st.session_state['messages']))
        st.metric("MCP", "✅" if st.session_state.get('mcp_status') == 'running' else "❌")
        
        st.divider()
        
        if st.button("📝 Chat mới", use_container_width=True, type="primary"):
            st.session_state["messages"] = []
            st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)