import os
import sys
import asyncio
from typing import Dict, Any, List, Optional
from enum import Enum

from dotenv import load_dotenv
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
from groq import Groq

# Ensure project root is on path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from Agent.math_agent import MathAgentState, build_graph as build_math_graph
from Agent.research_agent import ResearchAgentState, build_graph as build_research_graph
from Agent.tools.serper_tool import serper_scholar_search
from Agent.tools.llm_router import route_prompt, RoutingDecision
from Memory.long_term import LongTermMemoryManager
from Memory.short_term import ShortTermMemory

# Load environment variables first
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# =================== Configuration ===================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
print(f"🔍 GROQ_API_KEY found: {bool(GROQ_API_KEY)}")
groq_client: Optional[Groq] = None
if GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
        print("✅ Groq client initialized successfully")
    except Exception as e:
        print(f"⚠️ Failed to initialize Groq client: {e}")
        groq_client = None
else:
    print("⚠️ GROQ_API_KEY not found in environment")
    groq_client = None

# =================== Agent Types ===================
class AgentType(str, Enum):
    MATH = "math"
    RESEARCH = "research" 
    OCR = "ocr"
    GENERAL = "general"

# =================== Master State ===================
class MasterAgentState(BaseModel):
    user_prompt: str = ""
    agent_type: Optional[AgentType] = None
    reasoning: str = ""
    confidence: float = 0.0
    context_analysis: Dict[str, Any] = {}
    result: str = ""
    error: str = ""
    # Memory context
    short_term_context: str = ""
    long_term_context: str = ""
    relevant_memories: List[Dict[str, Any]] = []

# =================== Agent Registry ===================
# Global memory instances (singleton pattern)
_global_long_term_memory = None
_global_short_term_memory = None

def get_long_term_memory():
    """Get global long-term memory instance."""
    global _global_long_term_memory
    if _global_long_term_memory is None:
        _global_long_term_memory = LongTermMemoryManager()
    return _global_long_term_memory

def get_short_term_memory():
    """Get global short-term memory instance."""
    global _global_short_term_memory
    if _global_short_term_memory is None:
        _global_short_term_memory = ShortTermMemory()
    return _global_short_term_memory

class AgentRegistry:
    def __init__(self):
        self.agents = {
            AgentType.MATH: self._run_math_agent,
            AgentType.RESEARCH: self._run_research_agent,
            AgentType.OCR: self._run_ocr_agent,
            AgentType.GENERAL: self._run_general_agent,
        }
        # Use global memory instances
        self.long_term_memory = get_long_term_memory()
        self.short_term_memory = get_short_term_memory()
    
    async def _run_math_agent(self, state: MasterAgentState) -> str:
        """Run math agent for mathematical problems"""
        try:
            # Add to short-term memory
            self.short_term_memory.add_user_message(state.user_prompt, {"agent_type": "math"})
            
            # Search for similar math problems in long-term memory
            similar_problems = await self.long_term_memory.retrieve_memories(
                query=state.user_prompt,
                memory_type="math_solution",
                max_results=3
            )
            
            # Skip similar problems display - focus only on the requested problem
            memory_context = ""
            
            # Run math agent with memory context
            math_graph = build_math_graph().compile()
            
            # Use short_term_context if available (contains Notion problem), otherwise use user_prompt
            problem_text = state.short_term_context if state.short_term_context else state.user_prompt
            
            math_state = MathAgentState(
                problem_text=problem_text, 
                use_research=True
            )
            result_state = await math_graph.ainvoke(math_state)
            
            if isinstance(result_state, dict):
                result_state = MathAgentState(**result_state)
            
            # Store the solution in long-term memory
            await self.long_term_memory.store_math_solution(
                problem=state.user_prompt,
                solution=result_state.solution_text,
                method="LangGraph + Groq",
                importance=0.8
            )
            
            # Add assistant response to short-term memory
            self.short_term_memory.add_assistant_message(
                f"=== LỜI GIẢI TOÁN ===\n{result_state.solution_text}",
                {"agent_type": "math", "memory_stored": True}
            )
            
            return result_state.solution_text
        except Exception as e:
            return f"Lỗi khi chạy math agent: {e}"
    
    async def _run_research_agent(self, state: MasterAgentState) -> str:
        """Run research agent for general research questions"""
        try:
            # Add to short-term memory
            self.short_term_memory.add_user_message(state.user_prompt, {"agent_type": "research"})
            
            # Search for related research in long-term memory
            related_research = self.long_term_memory.retrieve_memories(
                query=state.user_prompt,
                memory_type="research",
                max_results=3
            )
            
            # Build context from memories
            memory_context = ""
            if related_research:
                memory_context = "=== NGHIÊN CỨU LIÊN QUAN ===\n"
                for i, research in enumerate(related_research, 1):
                    memory_context += f"{i}. {research['content'][:200]}...\n"
                memory_context += "\n"
            
            # Run research agent
            research_graph = build_research_graph().compile()
            research_state = ResearchAgentState(question=state.user_prompt)
            result_state = await research_graph.ainvoke(research_state)
            
            if isinstance(result_state, dict):
                result_state = ResearchAgentState(**result_state)
            
            # Extract sources from research result
            sources = []
            if "Sources:" in result_state.answer:
                sources_section = result_state.answer.split("Sources:")[1]
                sources = [line.strip() for line in sources_section.split('\n') if line.strip()]
            
            # Store research findings in long-term memory
            self.long_term_memory.store_research_finding(
                topic=state.user_prompt,
                findings=result_state.answer,
                sources=sources,
                importance=0.7
            )
            
            # Add assistant response to short-term memory
            self.short_term_memory.add_assistant_message(
                f"=== KẾT QUẢ NGHIÊN CỨU ===\n{result_state.answer}",
                {"agent_type": "research", "memory_stored": True}
            )
            
            return f"{memory_context}=== KẾT QUẢ NGHIÊN CỨU ===\n{result_state.answer}"
        except Exception as e:
            return f"Lỗi khi chạy research agent: {e}"
    
    async def _run_ocr_agent(self, state: MasterAgentState) -> str:
        """Run OCR agent for image processing requests"""
        # Extract image path from prompt if available
        prompt_lower = state.user_prompt.lower()
        image_path = None
        
        # Look for common image path patterns
        import re
        path_patterns = [
            r'ảnh\s+([^\s]+\.(jpg|jpeg|png|bmp|tiff))',
            r'hình\s+([^\s]+\.(jpg|jpeg|png|bmp|tiff))',
            r'image\s+([^\s]+\.(jpg|jpeg|png|bmp|tiff))',
            r'file\s+([^\s]+\.(jpg|jpeg|png|bmp|tiff))',
            r'([^\s]+\.(jpg|jpeg|png|bmp|tiff))'
        ]
        
        for pattern in path_patterns:
            match = re.search(pattern, prompt_lower)
            if match:
                image_path = match.group(1)
                break
        
        if not image_path:
            return "=== OCR AGENT ===\nOCR agent cần đường dẫn ảnh cụ thể. Vui lòng cung cấp đường dẫn file ảnh để xử lý.\n\nVí dụ: 'Xử lý ảnh image.jpg' hoặc 'OCR file document.png'"
        
        # Check if file exists
        if not os.path.exists(image_path):
            return f"=== OCR AGENT ===\n❌ Không tìm thấy file ảnh: {image_path}\nVui lòng kiểm tra đường dẫn file."
        
        try:
            # Import OCR components
            sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
            from OCR.ocr_model import VinternClient, wait_until_ready
            from MCP.notion_mcp_client import NotionMCPClient
            
            # OCR API configuration
            api_url = "https://rational-vocal-piglet.ngrok-free.app"
            notion_token = os.getenv("NOTION_TOKEN")
            page_id = "26974e97-008f-80ac-b77d-dbc6a7fe7726"  # Default page ID
            
            client = VinternClient(api_url)
            
            # Wait for OCR API to be ready
            print("🔎 Đợi OCR API sẵn sàng…")
            health = wait_until_ready(api_url)
            print("Health check:", health)
            
            # Upload image to OCR server
            print("📤 Upload ảnh:", image_path)
            resp = client.upload_image(image_path)
            print("Raw resp:", resp)
            
            if resp.get("status") != "ok":
                return f"=== OCR AGENT ===\n❌ Lỗi OCR: {resp.get('msg', resp)}"
            
            # Format OCR result
            blocks = resp.get("blocks", [])
            if not blocks:
                ocr_text = resp.get("merged_text", "")
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
                ocr_text = "\n\n".join(formatted)
            
            if not ocr_text.strip():
                return "=== OCR AGENT ===\n⚠️ OCR server không trả về text có thể dùng!"
            
            # Write to Notion if token is available
            if notion_token:
                try:
                    notion_client = NotionMCPClient(os.path.join(os.path.dirname(__file__), "..", "MCP", "mcp_server.py"), notion_token)
                    async with notion_client.connect():
                        text_block = f"📄 Kết quả OCR từ {image_path}:\n\n{ocr_text}"
                        await notion_client.update_page(page_id, content=text_block)
                        print("✅ Đã ghi OCR vào Notion page:", page_id)
                except Exception as e:
                    print(f"⚠️ Không thể ghi vào Notion: {e}")
            
            return f"=== OCR AGENT ===\n📖 Kết quả OCR từ {image_path}:\n\n{ocr_text}"
            
        except Exception as e:
            return f"=== OCR AGENT ===\n❌ Lỗi khi xử lý OCR: {e}\n\nVui lòng kiểm tra:\n- Đường dẫn file ảnh\n- Kết nối OCR API\n- Cấu hình Notion token"
    
    async def _run_general_agent(self, state: MasterAgentState) -> str:
        """Run general agent using Groq for other questions"""
        if groq_client is None:
            return "=== TRỢ LÝ TỔNG QUÁT ===\n(GROQ chưa cấu hình) Tôi có thể giúp bạn với các câu hỏi tổng quát khi có API key."
        
        try:
            # Add to short-term memory
            self.short_term_memory.add_user_message(state.user_prompt, {"agent_type": "general"})
            
            # Search for relevant knowledge in long-term memory
            relevant_knowledge = await self.long_term_memory.retrieve_memories(
                query=state.user_prompt,
                memory_type="knowledge",
                max_results=3
            )
            
            # Get conversation context
            conversation_context = self.short_term_memory.get_conversation_context()
            
            # Build context for LLM
            context_messages = [
                {"role": "system", "content": "Bạn là trợ lý AI thông minh, hãy trả lời câu hỏi một cách chi tiết và hữu ích."}
            ]
            
            # Add relevant knowledge if available
            if relevant_knowledge:
                knowledge_context = "=== KIẾN THỨC LIÊN QUAN ===\n"
                for i, knowledge in enumerate(relevant_knowledge, 1):
                    knowledge_context += f"{i}. {knowledge['content'][:200]}...\n"
                knowledge_context += "\n"
                
                context_messages.append({
                    "role": "system", 
                    "content": f"{knowledge_context}Hãy sử dụng thông tin trên để trả lời câu hỏi."
                })
            
            # Add conversation context if available
            if conversation_context:
                context_messages.append({
                    "role": "system",
                    "content": f"Ngữ cảnh cuộc trò chuyện:\n{conversation_context}"
                })
            
            # Add user question
            context_messages.append({"role": "user", "content": state.user_prompt})
            
            completion = groq_client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=context_messages,
                temperature=0.7,
                max_completion_tokens=1024,
                stream=True
            )
            
            result_parts = []
            for chunk in completion:
                delta = getattr(chunk.choices[0], "delta", None)
                if delta and getattr(delta, "content", None):
                    result_parts.append(delta.content)
            
            result_text = ''.join(result_parts)
            
            # Store useful knowledge in long-term memory
            if len(result_text) > 100:  # Only store substantial responses
                await self.long_term_memory.store_memory(
                    content=f"Q: {state.user_prompt}\nA: {result_text}",
                    memory_type="knowledge",
                    importance=0.6,
                    tags=["general", "qa"],
                    context="General knowledge question",
                    source="general_agent"
                )
            
            # Add assistant response to short-term memory
            self.short_term_memory.add_assistant_message(
                f"=== TRỢ LÝ TỔNG QUÁT ===\n{result_text}",
                {"agent_type": "general", "memory_stored": True}
            )
            
            return f"=== TRỢ LÝ TỔNG QUÁT ===\n{result_text}"
        except Exception as e:
            return f"Lỗi khi chạy general agent: {e}"

# =================== Master Agent Nodes ===================
async def analyze_prompt(state: MasterAgentState) -> MasterAgentState:
    """Analyze user prompt using semantic router for intelligent routing"""
    try:
        # Use semantic router for advanced analysis
        routing_decision = await route_prompt(state.user_prompt)
        
        state.agent_type = AgentType(routing_decision.agent_type)
        state.reasoning = routing_decision.reasoning
        state.confidence = routing_decision.confidence
        # Handle different routing decision types
        if hasattr(routing_decision, 'context_analysis'):
            state.context_analysis = routing_decision.context_analysis
        else:
            state.context_analysis = {"reasoning": routing_decision.reasoning}
        
        print(f"🤖 Chọn agent: {state.agent_type.value} (độ tin cậy: {state.confidence:.2f})")
        print(f"💭 Lý do: {state.reasoning}")
        
        # Show detailed analysis if confidence is low
        if state.confidence < 0.6:
            print("⚠️ Độ tin cậy thấp, có thể cần xem xét lại")
            if hasattr(routing_decision, 'context_analysis') and isinstance(routing_decision.context_analysis, dict):
                scores = routing_decision.context_analysis.get("scores", {})
                for agent, score_info in scores.items():
                    print(f"   {agent}: {score_info['score']:.2f} (semantic: {score_info['semantic']:.2f}, keyword: {score_info['keyword']:.2f})")
        
    except Exception as e:
        # Fallback to simple keyword matching
        print(f"⚠️ Lỗi semantic router: {e}, chuyển sang phân tích đơn giản")
        prompt_lower = state.user_prompt.lower()
        if any(word in prompt_lower for word in ["giải", "phương trình", "toán", "tính", "tính toán", "x^", "="]):
            state.agent_type = AgentType.MATH
            state.reasoning = "Phát hiện từ khóa toán học"
        elif any(word in prompt_lower for word in ["nghiên cứu", "tìm hiểu", "thông tin", "tin tức", "news"]):
            state.agent_type = AgentType.RESEARCH
            state.reasoning = "Phát hiện từ khóa nghiên cứu"
        elif any(word in prompt_lower for word in ["ocr", "ảnh", "hình", "image", "scan"]):
            state.agent_type = AgentType.OCR
            state.reasoning = "Phát hiện từ khóa OCR"
        else:
            state.agent_type = AgentType.GENERAL
            state.reasoning = "Câu hỏi tổng quát"
        
        state.confidence = 0.5
        state.context_analysis = {"fallback": True}
        print(f"🤖 Chọn agent: {state.agent_type.value} - {state.reasoning}")
    
    return state

async def route_to_agent(state: MasterAgentState) -> MasterAgentState:
    """Route to the selected specialized agent"""
    registry = AgentRegistry()
    
    if state.agent_type in registry.agents:
        try:
            # Get the agent method and call it with await
            agent_method = registry.agents[state.agent_type]
            state.result = await agent_method(state)
        except Exception as e:
            state.error = f"Lỗi khi chạy {state.agent_type.value} agent: {e}"
            state.result = f"❌ {state.error}"
    else:
        state.error = f"Agent {state.agent_type} không tồn tại"
        state.result = f"❌ {state.error}"
    
    return state

async def format_output(state: MasterAgentState) -> MasterAgentState:
    """Format and display the final result"""
    print(f"\n{'='*60}")
    print(f"🎯 Agent được chọn: {state.agent_type.value.upper()}")
    print(f"💭 Lý do: {state.reasoning}")
    print(f"📊 Độ tin cậy: {state.confidence:.2f}")
    
    # Show context analysis if available
    if state.context_analysis and not state.context_analysis.get("fallback"):
        context = state.context_analysis.get("context", {})
        if context:
            print(f"🔍 Phân tích ngữ cảnh:")
            print(f"   - Mục đích: {context.get('intent', 'unknown')}")
            print(f"   - Lĩnh vực: {context.get('domain', 'general')}")
            print(f"   - Độ phức tạp: {context.get('complexity', 'medium')}")
    
    print(f"{'='*60}")
    print(state.result)
    if state.error:
        print(f"\n⚠️ Lỗi: {state.error}")
    print(f"{'='*60}")
    return state

# =================== Master Graph ===================
def build_master_graph():
    graph = StateGraph(MasterAgentState)
    
    graph.add_node("analyze_prompt", analyze_prompt)
    graph.add_node("route_to_agent", route_to_agent)
    graph.add_node("format_output", format_output)
    
    graph.add_edge("analyze_prompt", "route_to_agent")
    graph.add_edge("route_to_agent", "format_output")
    graph.add_edge("format_output", END)
    
    graph.set_entry_point("analyze_prompt")
    return graph

# =================== CLI ===================
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Master Agent - Router thông minh cho các agent chuyên biệt")
    parser.add_argument("--prompt", required=True, help="Câu hỏi/yêu cầu của bạn")
    args = parser.parse_args()
    
    master_graph = build_master_graph().compile()
    init_state = MasterAgentState(user_prompt=args.prompt)
    final_state = await master_graph.ainvoke(init_state)
    
    return final_state

if __name__ == "__main__":
    asyncio.run(main())
