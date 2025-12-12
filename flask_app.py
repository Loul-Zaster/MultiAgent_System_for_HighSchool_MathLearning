"""
Flask application for Multi-Agent Math Learning System
Replaces Streamlit with a modern web interface
"""

# ============= Suppress TensorFlow warnings =============
# MUST be set BEFORE any imports that use TensorFlow
import os
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'  # Disable oneDNN custom operations
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'   # Suppress all TF logs (0=all, 1=info, 2=warning, 3=error only)

# Suppress Python warnings
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=FutureWarning)
# ========================================================

import sys
import asyncio
import json
import re
from datetime import datetime
from typing import Dict, List, Optional

from flask import Flask, render_template, request, jsonify, session, Response, stream_with_context
from flask_cors import CORS
from dotenv import load_dotenv

# Add paths
sys.path.append(os.path.join(os.path.dirname(__file__), "MCP"))
sys.path.append(os.path.dirname(__file__))

print("Starting imports...")
print("  → Importing from Agent.master_agent...")
try:
    from Agent.master_agent import build_master_graph, MasterAgentState
    print("  Agent.master_agent imported successfully")
except Exception as e:
    print(f"  Error importing Agent.master_agent: {e}")
    import traceback
    traceback.print_exc()
    raise

print("  → Importing from MCP.notion_mcp_client...")
try:
    from MCP.notion_mcp_client import NotionMCPClient
    print("  MCP.notion_mcp_client imported successfully")
except Exception as e:
    print(f"  Error importing MCP.notion_mcp_client: {e}")
    import traceback
    traceback.print_exc()
    raise

print("  → Importing from Memory.long_term...")
try:
    from Memory.long_term import LongTermMemoryManager
    print("  Memory.long_term imported successfully")
except Exception as e:
    print(f"  Error importing Memory.long_term: {e}")
    import traceback
    traceback.print_exc()
    raise

print("All imports completed successfully!")

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")
CORS(app)

# Configuration
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
project_root = os.path.abspath(os.getcwd())
server_path = os.path.abspath(os.path.join(project_root, "MCP", "mcp_server.py"))

# Helper function to get Notion token (from session only - user must connect)
def get_notion_token():
    """Get Notion token from session only. User must connect via UI to use MCP features."""
    # Only use session API key - do not fallback to .env
    # This ensures users must explicitly connect via UI
    return session.get('notion_api_key')

# Global state (in production, use Redis or database)
sessions: Dict[str, Dict] = {}

def get_session(session_id: str) -> Dict:
    """Get or create session"""
    if session_id not in sessions:
        sessions[session_id] = {
            "messages": [],
            "notion_page_id": "",
            "notion_problem": "",
            "notion_problems": {},
            "selected_problem": None,
            "master_agent_context": "",
            "mcp_status": "stopped"
        }
        print(f"Created new session: {session_id}")
    return sessions[session_id]

def render_latex_content(content: str) -> str:
    """Clean LaTeX content for proper rendering - PRESERVE LaTeX delimiters"""
    try:
        # Remove LATEX placeholders that LLM might return (these are errors)
        content = re.sub(r'LATEXINLINE\d*', '[LaTeX formula]', content, flags=re.IGNORECASE)
        content = re.sub(r'LATEXDISPLAY\d*', '[LaTeX formula]', content, flags=re.IGNORECASE)
        
        # Fix broken LaTeX patterns
        content = re.sub(r'\\frac\{([^}]*)\*\*\{([^}]*)\*\*\}', r'\\frac{\1}{\2}', content)
        content = re.sub(r'\\binom\{([^}]*)\*\*\{([^}]*)\*\*\}', r'\\binom{\1}{\2}', content)
        content = re.sub(r'\\sum_\{([^}]*)\*\*}', r'\\sum_{\1}', content)
        content = re.sub(r'\\begin\{aligned\*\*}', r'\\begin{aligned}', content)
        content = re.sub(r'\\end\{aligned\*\*}', r'\\end{aligned}', content)
        
        # CRITICAL: DO NOT modify LaTeX delimiters ($, $$, \[, \()
        # The frontend JavaScript will handle rendering them properly
        # We only clean up broken patterns, not valid LaTeX
        
    except Exception as e:
        print(f"Warning: LaTeX processing error: {e}")
    
    return content

async def run_master_agent(prompt: str, context: str = "", session_id: str = "") -> dict:
    """Run master agent and return response (dict with reply and trace)"""
    try:
        session_data = get_session(session_id)
        master_graph = build_master_graph().compile()
        
        # Build context with selected problem info
        full_context = context
        if session_data.get("selected_problem"):
            selected = session_data["selected_problem"]
            problem_content = session_data["notion_problems"].get(selected, "")
            if any(keyword in prompt.lower() for keyword in [f"bài số {selected.split()[-1]}", f"bài {selected.split()[-1]}", selected.lower()]):
                full_context = f"{selected}\n\n{problem_content}"
            else:
                full_context = context
        
        init_state = MasterAgentState(
            user_prompt=prompt,
            short_term_context=full_context,
            long_term_context=session_data.get("master_agent_context", ""),
            session_id=session_id  # Pass session_id for context isolation
        )
        
        result_state = await master_graph.ainvoke(init_state)
        
        if isinstance(result_state, dict):
            return {
                "reply": result_state.get('result', 'Không có kết quả'),
                "trace": result_state.get('trace', [])
            }
        else:
            res = result_state.result if hasattr(result_state, 'result') else str(result_state)
            trace = getattr(result_state, 'trace', [])
            return {
                "reply": res,
                "trace": trace
            }
            
    except Exception as e:
        return f"Lỗi Master Agent: {e}"

async def fetch_problem_from_notion(page_id: str) -> dict:
    """Fetch and parse problems from Notion page"""
    notion_token = get_notion_token()
    if not notion_token:
        raise ValueError("Notion API key not configured. Please connect Notion in Settings > Integrations.")
    notion = NotionMCPClient(server_path, notion_token)
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
        problems = {}
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
            problems["Toàn bộ"] = full_content
        
        return {
            "full_content": full_content,
            "problems": problems
        }

async def append_markdown_to_notion(page_id: str, content: str, mode: str = "add") -> str:
    """Append or replace markdown content on a Notion page via MCP"""
    notion_token = get_notion_token()
    if not notion_token:
        raise ValueError("Notion API key not configured. Please connect Notion in Settings > Integrations.")
    client = NotionMCPClient(server_path, notion_token)
    async with client.connect():
        return await client.update_page(page_id=page_id, content=content, mode=mode)

# =================== Routes ===================

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    data = request.json
    prompt = data.get('prompt', '')
    session_id = data.get('session_id', session.get('session_id', 'default'))
    
    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400
    
    session_data = get_session(session_id)
    
    # No longer combining OCR with prompt - OCR is saved to Notion instead
    # User can ask Master Agent to read from Notion if needed
    
    # Add user message
    session_data["messages"].append({
        "role": "user",
        "content": prompt,
        "timestamp": datetime.now().isoformat()
    })
    
    # Run master agent
    try:
        reply_data = asyncio.run(run_master_agent(
            prompt,  # Use original prompt, not combined
            session_data.get("master_agent_context", ""),
            session_id
        ))
        
        reply = reply_data.get("reply", "")
        trace = reply_data.get("trace", [])
        
        # Debug: log raw reply before processing
        print("=" * 80)
        print("DEBUG: Raw reply from master agent (first 1000 chars):")
        print(reply[:1000])
        print("=" * 80)
        print(f"DEBUG: Raw reply contains:")
        print(f"  - $$: {reply.count('$$')}")
        print(f"  - $ (single): {reply.count('$') - reply.count('$$') * 2}")
        print(f"  - \\[: {reply.count('\\[')}")
        print(f"  - \\(: {reply.count('\\(')}")
        print(f"  - LATEXINLINE: {reply.count('LATEXINLINE')}")
        print(f"  - LATEXDISPLAY: {reply.count('LATEXDISPLAY')}")
        print("=" * 80)
        
        # Clean LaTeX - but preserve delimiters
        reply = render_latex_content(reply)
        
        # Debug: log after processing
        print("=" * 80)
        print("DEBUG: Reply after render_latex_content (first 1000 chars):")
        print(reply[:1000])
        print("=" * 80)
        print(f"DEBUG: After processing contains:")
        print(f"  - $$: {reply.count('$$')}")
        print(f"  - $ (single): {reply.count('$') - reply.count('$$') * 2}")
        print(f"  - [LaTeX formula]: {reply.count('[LaTeX formula]')}")
        print("=" * 80)
        
        # Add assistant message
        session_data["messages"].append({
            "role": "assistant",
            "content": reply,
            "timestamp": datetime.now().isoformat()
        })
        
        # Debug: Check what will be sent in JSON
        import json as json_module
        json_test = json_module.dumps({"reply": reply})
        print("=" * 80)
        print("DEBUG: JSON serialization test:")
        print(f"  - Reply length: {len(reply)}")
        print(f"  - JSON length: {len(json_test)}")
        # Check if backslashes are preserved
        if '\\[' in json_test:
            print(f"  - JSON contains \\[: {json_test.count('\\\\[')} occurrences")
        if '\\(' in json_test:
            print(f"  - JSON contains \\(: {json_test.count('\\\\(')} occurrences")
        # Show a sample
        sample_idx = json_test.find('\\\\[') if '\\\\[' in json_test else json_test.find('\\[') if '\\[' in json_test else 0
        if sample_idx > 0:
            print(f"  - Sample (index {sample_idx}): {json_test[sample_idx-10:sample_idx+50]}")
        print("=" * 80)
        
        # Optionally save to Notion
        page_id = session_data.get("notion_page_id", "").strip()
        if page_id:
            try:
                md = f"""
### 💬 Trao đổi

**Người dùng:**

{prompt}

**Trợ lý:**

{reply}
""".strip()
                asyncio.run(append_markdown_to_notion(page_id, md, mode="add"))
            except Exception as e:
                print(f"Không lưu được vào Notion: {e}")
        
        return jsonify({
            "success": True,
            "reply": reply,
            "trace": trace,
            "session_id": session_id
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    """Stream chat responses (SSE)"""
    data = request.json
    prompt = data.get('prompt', '')
    session_id = data.get('session_id', session.get('session_id', 'default'))
    
    def generate():
        try:
            session_data = get_session(session_id)
            
            # Add user message
            session_data["messages"].append({
                "role": "user",
                "content": prompt,
                "timestamp": datetime.now().isoformat()
            })
            
            yield f"data: {json.dumps({'type': 'user_message', 'content': prompt})}\n\n"
            
            # Run master agent (for now, non-streaming)
            reply = asyncio.run(run_master_agent(
                prompt,
                session_data.get("master_agent_context", ""),
                session_id
            ))
            
            reply = render_latex_content(reply)
            
            # Stream response word by word (simplified)
            words = reply.split(' ')
            for i, word in enumerate(words):
                chunk = word + (' ' if i < len(words) - 1 else '')
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
            
            # Final message
            session_data["messages"].append({
                "role": "assistant",
                "content": reply,
                "timestamp": datetime.now().isoformat()
            })
            
            yield f"data: {json.dumps({'type': 'done', 'content': reply})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/api/messages', methods=['GET'])
def get_messages():
    """Get chat messages for session"""
    session_id = request.args.get('session_id', session.get('session_id', 'default'))
    session_data = get_session(session_id)
    messages = session_data.get("messages", [])
    print(f"📨 Getting messages for session {session_id}: {len(messages)} messages")
    return jsonify({
        "messages": messages,
        "session_id": session_id,
        "count": len(messages)
    })

@app.route('/api/messages/clear', methods=['POST'])
def clear_messages():
    """Clear chat messages"""
    data = request.json
    session_id = data.get('session_id', session.get('session_id', 'default'))
    session_data = get_session(session_id)
    session_data["messages"] = []
    session_data["master_agent_context"] = ""
    return jsonify({"success": True})

@app.route('/api/notion/fetch', methods=['POST'])
def notion_fetch():
    """Fetch problems from Notion"""
    data = request.json
    page_id = data.get('page_id', '')
    session_id = data.get('session_id', session.get('session_id', 'default'))
    
    if not page_id:
        return jsonify({"error": "Page ID is required"}), 400
    
    try:
        result = asyncio.run(fetch_problem_from_notion(page_id))
        session_data = get_session(session_id)
        session_data["notion_page_id"] = page_id
        session_data["notion_problem"] = result["full_content"]
        session_data["notion_problems"] = result["problems"]
        
        return jsonify({
            "success": True,
            "full_content": result["full_content"],
            "problems": result["problems"],
            "count": len(result["problems"])
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/notion/select-problem', methods=['POST'])
def notion_select_problem():
    """Select a problem from Notion"""
    data = request.json
    problem_key = data.get('problem_key', '')
    session_id = data.get('session_id', session.get('session_id', 'default'))
    
    session_data = get_session(session_id)
    
    if problem_key in session_data["notion_problems"]:
        session_data["selected_problem"] = problem_key
        problem_content = session_data["notion_problems"][problem_key]
        session_data["master_agent_context"] = f"Đang xử lý {problem_key}:\n\n{problem_content}"
        
        # Add to chat
        session_data["messages"].append({
            "role": "user",
            "content": f"📚 **{problem_key}**\n\n{problem_content}",
            "timestamp": datetime.now().isoformat()
        })
        
        return jsonify({
            "success": True,
            "problem_key": problem_key,
            "problem_content": problem_content
        })
    else:
        return jsonify({
            "success": False,
            "error": "Problem not found"
        }), 404

@app.route('/api/memory/stats', methods=['GET'])
def memory_stats():
    """Get memory statistics"""
    try:
        ltm = LongTermMemoryManager()
        memories = ltm.list_all_memories(limit=10)
        return jsonify({
            "success": True,
            "total": len(memories),
            "memories": memories[:10]
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/mcp/status', methods=['GET'])
def mcp_status():
    """Get MCP server status"""
    session_id = request.args.get('session_id', session.get('session_id', 'default'))
    session_data = get_session(session_id)
    return jsonify({
        "status": session_data.get("mcp_status", "stopped")
    })

@app.route('/api/settings/update-api-key', methods=['POST'])
def update_api_key():
    """Update API key in session"""
    try:
        data = request.json
        api_type = data.get('type')  # 'notion' or 'google'
        api_key = data.get('key', '')
        
        if api_type == 'notion':
            session['notion_api_key'] = api_key
            return jsonify({"success": True, "message": "Notion API key updated"})
        elif api_type == 'google':
            session['google_api_key'] = api_key
            return jsonify({"success": True, "message": "Google API key updated"})
        else:
            return jsonify({"success": False, "error": "Invalid API type"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/mcp/list-resources', methods=['GET'])
def mcp_list_resources():
    """List all Notion resources (pages and databases)"""
    try:
        notion_token = get_notion_token()
        if not notion_token:
            return jsonify({"success": False, "error": "NOTION_TOKEN not configured. Please connect Notion in Settings > Integrations."}), 400
        
        notion = NotionMCPClient(server_path, notion_token)
        resources = asyncio.run(notion.list_resources())
        
        formatted_resources = []
        for resource in resources:
            obj_type = resource.get("object", "").lower()
            resource_type = "page" if obj_type == "page" else "database" if obj_type == "database" else "unknown"
            
            name = "Untitled"
            if obj_type == "page":
                properties = resource.get("properties", {})
                for prop_name, prop_value in properties.items():
                    if prop_value.get("type") == "title":
                        title_array = prop_value.get("title", [])
                        if title_array:
                            name = title_array[0].get("plain_text", "Untitled")
                            break
                if name == "Untitled":
                    name = f"Page {resource.get('id', '')[:8]}"
            elif obj_type == "database":
                title_array = resource.get("title", [])
                if title_array:
                    name = title_array[0].get("plain_text", "Untitled")
                else:
                    name = f"Database {resource.get('id', '')[:8]}"
            
            resource_id = resource.get("id", "")
            uri = f"notion://{obj_type}/{resource_id}"
            
            formatted_resources.append({
                "name": name,
                "uri": uri,
                "type": resource_type,
                "id": resource_id,
                "url": resource.get("url", "")
            })
        
        return jsonify({
            "success": True,
            "resources": formatted_resources
        })
    except Exception as e:
        print(f"Error listing resources: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/mcp/read-resource', methods=['POST'])
def mcp_read_resource():
    """Read content from a Notion resource"""
    try:
        data = request.json
        resource_uri = data.get('uri')
        
        if not resource_uri:
            return jsonify({"success": False, "error": "Resource URI is required"}), 400
        
        notion_token = get_notion_token()
        if not notion_token:
            return jsonify({"success": False, "error": "NOTION_TOKEN not configured"}), 400
        
        print(f"Reading resource: {resource_uri}")
        notion = NotionMCPClient(server_path, notion_token)
        content = asyncio.run(notion.read_resource(resource_uri))
        
        print(f"Content length: {len(content) if content else 0}")
        print(f"Content preview: {content[:200] if content else 'EMPTY'}")
        
        if not content or not content.strip():
            return jsonify({
                "success": False,
                "error": "Page content is empty or could not be retrieved",
                "content": "",
                "uri": resource_uri
            })
        
        return jsonify({
            "success": True,
            "content": content,
            "uri": resource_uri
        })
    except Exception as e:
        print(f"Error reading resource: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/mcp/search', methods=['POST'])
def mcp_search():
    """Search Notion"""
    try:
        data = request.json
        query = data.get('query', '')
        filter_type = data.get('filter', '')
        
        if not query:
            return jsonify({"success": False, "error": "Search query is required"}), 400
        
        notion_token = get_notion_token()
        if not notion_token:
            return jsonify({"success": False, "error": "NOTION_TOKEN not configured"}), 400
        
        notion = NotionMCPClient(server_path, notion_token)
        result = asyncio.run(notion.search_notion(query, filter_type if filter_type else None))
        
        try:
            if "Search results" in result:
                json_start = result.find("{")
                if json_start >= 0:
                    json_str = result[json_start:]
                    json_end = json_str.rfind("}") + 1
                    if json_end > 0:
                        parsed = json.loads(json_str[:json_end])
                        return jsonify({
                            "success": True,
                            "results": parsed.get("results", []),
                            "raw": result
                        })
        except:
            pass
        
        return jsonify({
            "success": True,
            "results": [],
            "raw": result
        })
    except Exception as e:
        print(f"Error searching: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/mcp/query-database', methods=['POST'])
def mcp_query_database():
    """Query a Notion database"""
    try:
        data = request.json
        database_id = data.get('database_id')
        page_size = data.get('page_size', 10)
        
        if not database_id:
            return jsonify({"success": False, "error": "Database ID is required"}), 400
        
        notion_token = get_notion_token()
        if not notion_token:
            return jsonify({"success": False, "error": "NOTION_TOKEN not configured"}), 400
        
        notion = NotionMCPClient(server_path, notion_token)
        result = asyncio.run(notion.query_database(database_id, page_size=page_size))
        
        return jsonify({
            "success": True,
            "result": result
        })
    except Exception as e:
        print(f"Error querying database: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/notion/create-page', methods=['POST'])
def notion_create_page():
    """Create a new Notion page"""
    try:
        data = request.json
        title = data.get('title')
        parent_id = data.get('parent_id')
        content = data.get('content', '')
        
        if not title or not parent_id:
            return jsonify({"success": False, "error": "Title and parent_id are required"}), 400
        
        notion_token = get_notion_token()
        if not notion_token:
            return jsonify({"success": False, "error": "NOTION_TOKEN not configured"}), 400
        
        notion = NotionMCPClient(server_path, notion_token)
        
        async def create_page_with_connection():
            async with notion.connect():
                return await notion.create_page(title, parent_id, content=content)
        
        result = asyncio.run(create_page_with_connection())
        
        return jsonify({
            "success": True,
            "result": result
        })
    except Exception as e:
        print(f"Error creating page: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/notion/update-page', methods=['POST'])
def notion_update_page():
    """Update an existing Notion page"""
    try:
        data = request.json
        page_id = data.get('page_id')
        content = data.get('content', '')
        mode = data.get('mode', 'add')  # 'add' or 'edit'
        title = data.get('title')
        
        if not page_id:
            return jsonify({"success": False, "error": "page_id is required"}), 400
        
        notion_token = get_notion_token()
        if not notion_token:
            return jsonify({"success": False, "error": "NOTION_TOKEN not configured"}), 400
        
        notion = NotionMCPClient(server_path, notion_token)
        
        async def update_page_with_connection():
            async with notion.connect():
                return await notion.update_page(page_id, title=title, content=content, mode=mode)
        
        result = asyncio.run(update_page_with_connection())
        
        return jsonify({
            "success": True,
            "result": result
        })
    except Exception as e:
        print(f"Error updating page: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/session/new', methods=['POST'])
def new_session():
    """Create a new session"""
    import uuid
    session_id = str(uuid.uuid4())
    get_session(session_id)  # Initialize
    return jsonify({
        "success": True,
        "session_id": session_id
    })

@app.route('/api/upload-file', methods=['POST'])
def upload_file():
    """
    Handle file upload (PDF/Image) for OCR processing.
    NEW WORKFLOW: Upload → OCR → Store in session → Wait for user prompt
    """
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "error": "Empty filename"}), 400
        
        # Get session ID
        session_id = request.form.get('session_id', session.get('session_id', 'default'))
        
        # Check file type
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in ['.pdf', '.png', '.jpg', '.jpeg']:
            return jsonify({"success": False, "error": "Only PDF and image files are supported"}), 400
        
        # Validate file size (max 20MB)
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > 20 * 1024 * 1024:  # 20MB
            return jsonify({"success": False, "error": "File too large (max 20MB)"}), 400
        
        # Save uploaded file temporarily
        upload_folder = os.path.join(project_root, "uploads")
        os.makedirs(upload_folder, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{file.filename}"
        file_path = os.path.join(upload_folder, safe_filename)
        file.save(file_path)
        
        print(f"📁 File uploaded: {file_path}")
        
        # Process OCR based on file type
        ocr_result = None
        
        if file_ext == '.pdf':
            # Use async OCR client for PDF
            try:
                from OCR.async_ocr_client import AsyncOCRClient
                
                ocr_api_url = os.getenv("OCR_API_URL", "https://catina-cnemial-uninvincibly.ngrok-free.dev")
                ocr_client = AsyncOCRClient(base_url=ocr_api_url, timeout=300)
                
                print(f"📤 Uploading PDF to OCR server...")
                job_id = ocr_client.upload_pdf(file_path)
                
                print(f"⏳ Waiting for OCR processing (Job ID: {job_id})...")
                # FIX: Remove verbose argument
                ocr_client.poll_until_complete(job_id)
                
                print(f"📥 Fetching OCR result...")
                ocr_result = ocr_client.get_result(job_id)
                print(f"✅ OCR complete: {len(ocr_result)} characters extracted")
                
            except Exception as e:
                print(f"❌ OCR processing failed: {e}")
                if os.path.exists(file_path):
                    os.remove(file_path)
                return jsonify({"success": False, "error": f"OCR processing failed: {str(e)}"}), 500
        
        else:
            # For images, use sync OCR (VinternClient)
            try:
                from OCR.ocr_model import VinternClient
                
                ocr_api_url = os.getenv("OCR_API_URL", "https://rational-vocal-piglet.ngrok-free.app")
                client = VinternClient(ocr_api_url)
                
                print(f"📤 Uploading image to OCR server...")
                resp = client.upload_image(file_path)
                
                if resp.get("status") != "ok":
                    raise RuntimeError(f"OCR failed: {resp.get('msg', resp)}")
                
                # Format blocks
                blocks = resp.get("blocks", [])
                if not blocks:
                    ocr_result = resp.get("merged_text", "")
                else:
                    formatted = []
                    for b in blocks:
                        text = b.get("text", "").strip()
                        btype = b.get("type")
                        if not text:
                            continue
                        if btype == "latex":
                            formatted.append(f"$$\n{text}\n$$")
                        else:
                            lines = [line.strip() for line in text.splitlines()]
                            joined = " ".join(l for l in lines if l)
                            formatted.append(joined)
                    ocr_result = "\n\n".join(formatted)
                
                print(f"✅ Image OCR complete: {len(ocr_result)} characters extracted")
                
            except Exception as e:
                print(f"❌ Image OCR failed: {e}")
                if os.path.exists(file_path):
                    os.remove(file_path)
                return jsonify({"success": False, "error": f"Image OCR failed: {str(e)}"}), 500
        
        # Clean up uploaded file
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Save OCR result to Notion instead of session
        try:
            from MCP.notion_mcp_client import NotionMCPClient
            
            notion_token = get_notion_token()
            if not notion_token:
                print("⚠️ No Notion token found, skipping Notion save")
                # Still return success but note that Notion save was skipped
                return jsonify({
                    "success": True,
                    "filename": file.filename,
                    "ocr_text": ocr_result,
                    "ocr_preview": ocr_result[:500] + ("..." if len(ocr_result) > 500 else ""),
                    "char_count": len(ocr_result),
                    "session_id": session_id,
                    "notion_saved": False,
                    "message": "OCR completed but Notion token not found"
                })
            
            print(f"💾 Saving OCR result to Notion...")
            mcp_client = NotionMCPClient(server_path, notion_token)
            
            # Create page title from filename
            page_title = f"OCR - {file.filename} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            # Create Notion page with OCR content
            result = mcp_client.create_page(
                title=page_title,
                content=ocr_result,
                parent_page_id=None  # Will use default workspace
            )
            
            page_id = result.get("page_id") if result and result.get("success") else None
            
            if page_id:
                print(f"✅ Saved to Notion page: {page_id}")
                
                # Store Notion page reference in session
                session_data = get_session(session_id)
                session_data["last_ocr_page"] = {
                    "page_id": page_id,
                    "filename": file.filename,
                    "page_title": page_title,
                    "char_count": len(ocr_result),
                    "created_at": datetime.now().isoformat()
                }
                
                return jsonify({
                    "success": True,
                    "filename": file.filename,
                    "ocr_preview": ocr_result[:500] + ("..." if len(ocr_result) > 500 else ""),
                    "char_count": len(ocr_result),
                    "session_id": session_id,
                    "notion_saved": True,
                    "notion_page_id": page_id,
                    "notion_page_title": page_title,
                    "message": f"OCR completed and saved to Notion: '{page_title}'"
                })
            else:
                print(f"❌ Failed to save to Notion")
                return jsonify({
                    "success": True,  # OCR succeeded
                    "filename": file.filename,
                    "ocr_text": ocr_result,
                    "ocr_preview": ocr_result[:500] + ("..." if len(ocr_result) > 500 else ""),
                    "char_count": len(ocr_result),
                    "session_id": session_id,
                    "notion_saved": False,
                    "message": "OCR completed but failed to save to Notion"
                })
                
        except Exception as e:
            print(f"⚠️ Notion save error: {e}")
            import traceback
            traceback.print_exc()
            
            # Still return success for OCR, just warn about Notion
            return jsonify({
                "success": True,  # OCR succeeded
                "filename": file.filename,
                "ocr_text": ocr_result,
                "ocr_preview": ocr_result[:500] + ("..." if len(ocr_result) > 500 else ""),
                "char_count": len(ocr_result),
                "session_id": session_id,
                "notion_saved": False,
                "notion_error": str(e),
                "message": f"OCR completed but Notion save failed: {str(e)}"
            })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500





# ============================================================================
# OCR SIDEBAR ROUTES
# ============================================================================

@app.route('/api/ocr_upload', methods=['POST'])
def ocr_upload():
    """
    Handle OCR file upload for sidebar display.
    Does NOT push OCR text to chat - only returns for sidebar.
    """
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Empty filename"}), 400
        
        # Save file temporarily in OCR folder (per user's note)
        from werkzeug.utils import secure_filename
        import uuid
        
        ocr_folder = os.path.join(project_root, "OCR", "tmp")
        os.makedirs(ocr_folder, exist_ok=True)
        
        # Generate unique filename
        file_ext = os.path.splitext(file.filename)[1].lower()
        temp_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(ocr_folder, temp_filename)
        file.save(file_path)
        
        print(f"📁 OCR file saved: {file_path}")
        
        # Process OCR based on file type
        ocr_result = None
        
        if file_ext == '.pdf':
            # Use async OCR client for PDF
            try:
                from OCR.async_ocr_client import AsyncOCRClient
                
                ocr_api_url = os.getenv("OCR_API_URL", "https://catina-cnemial-uninvincibly.ngrok-free.dev")
                ocr_client = AsyncOCRClient(base_url=ocr_api_url, timeout=300)
                
                print(f"📤 Processing PDF with async OCR...")
                job_id = ocr_client.upload_pdf(file_path)
                ocr_client.poll_until_complete(job_id)
                ocr_result = ocr_client.get_result(job_id)
                
                print(f"✅ PDF OCR complete: {len(ocr_result)} characters")
                
            except Exception as e:
                print(f"❌ PDF OCR failed: {e}")
                if os.path.exists(file_path):
                    os.remove(file_path)
                return jsonify({"error": f"PDF OCR failed: {str(e)}"}), 500
        
        else:
            # Use sync OCR for images
            try:
                from OCR.ocr_model import VinternClient
                
                ocr_api_url = os.getenv("OCR_API_URL", "https://catina-cnemial-uninvincibly.ngrok-free.dev")
                client = VinternClient(ocr_api_url)
                
                print(f"📤 Processing image with sync OCR...")
                resp = client.upload_image(file_path)
                
                if resp.get("status") != "ok":
                    raise RuntimeError(f"OCR failed: {resp.get('msg', resp)}")
                
                # Format blocks
                blocks = resp.get("blocks", [])
                if not blocks:
                    ocr_result = resp.get("merged_text", "")
                else:
                    formatted = []
                    for b in blocks:
                        text = b.get("text", "").strip()
                        btype = b.get("type")
                        if not text:
                            continue
                        if btype == "latex":
                            formatted.append(f"$$\n{text}\n$$")
                        else:
                            lines = [line.strip() for line in text.splitlines()]
                            joined = " ".join(l for l in lines if l)
                            formatted.append(joined)
                    ocr_result = "\n\n".join(formatted)
                
                print(f"✅ Image OCR complete: {len(ocr_result)} characters")
                
            except Exception as e:
                print(f"❌ Image OCR failed: {e}")
                if os.path.exists(file_path):
                    os.remove(file_path)
                return jsonify({"error": f"Image OCR failed: {str(e)}"}), 500
        
        # Clean up temp file
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Generate OCR ID
        ocr_id = str(uuid.uuid4())
        
        # Return OCR result for sidebar display
        return jsonify({
            "ocr_id": ocr_id,
            "text": ocr_result,
            "meta": {
                "file_name": file.filename,
                "char_count": len(ocr_result),
                "processed_at": datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



if __name__ == '__main__':
    print("Starting Flask server...")
    print("   Server will be available at http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)



