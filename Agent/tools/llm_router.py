import os
import json
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
from groq import Groq

# =================== Configuration ===================
try:
    from dotenv import load_dotenv
    # Load from project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    load_dotenv(dotenv_path=os.path.join(project_root, ".env"))
except Exception as e:
    print(f"Could not load .env: {e}")
    pass

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client: Optional[Groq] = None
if GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        print(f"Failed to initialize Groq client in LLM router: {e}")
        groq_client = None
else:
    groq_client = None

# =================== Data Structures ===================
@dataclass
class AgentInfo:
    name: str
    description: str
    capabilities: List[str]
    examples: List[str]

@dataclass
class RoutingDecision:
    agent_type: str
    confidence: float
    reasoning: str
    alternative_agents: List[Dict[str, any]]

# =================== LLM Router ===================
class LLMRouter:
    def __init__(self):
        self.agents = self._initialize_agents()
    
    def _initialize_agents(self) -> Dict[str, AgentInfo]:
        """Define available agents with their capabilities"""
        return {
            "math": AgentInfo(
                name="Math Agent",
                description="Chuyên giải toán, phương trình, tính toán, phân tích số liệu và các bài toán toán học",
                capabilities=[
                    "Giải phương trình đại số và vi phân",
                    "Tính toán số học và đại số",
                    "Phân tích thống kê và xác suất",
                    "Vẽ đồ thị hàm số",
                    "Giải hệ phương trình tuyến tính",
                    "Tính toán ma trận và vector",
                    "Giải tích và đạo hàm",
                    "Hình học và không gian"
                ],
                examples=[
                    "Giải phương trình x^2 - 5x + 6 = 0",
                    "Tính đạo hàm của f(x) = x^3 + 2x^2 - 5x + 1",
                    "Tìm ma trận nghịch đảo của A = [[1,2],[3,4]]",
                    "Vẽ đồ thị hàm số y = sin(x)",
                    "Tính xác suất của biến cố ngẫu nhiên",
                    "Giải hệ phương trình tuyến tính 3 ẩn"
                ]
            ),
            "research": AgentInfo(
                name="Research Agent", 
                description="Nghiên cứu, tìm kiếm thông tin realtime, phân tích dữ liệu và tổng hợp báo cáo",
                capabilities=[
                    "Tìm kiếm thông tin realtime trên web",
                    "Phân tích xu hướng và thống kê",
                    "Tổng hợp báo cáo từ nhiều nguồn",
                    "Cập nhật tin tức mới nhất",
                    "Nghiên cứu thị trường và kinh tế",
                    "Phân tích dữ liệu và biểu đồ",
                    "So sánh và đánh giá thông tin"
                ],
                examples=[
                    "Tin tức mới nhất về AI tuần này",
                    "Phân tích xu hướng thị trường chứng khoán",
                    "Tìm hiểu về công nghệ blockchain",
                    "Báo cáo về tình hình kinh tế Việt Nam",
                    "Nghiên cứu về biến đổi khí hậu",
                    "So sánh các framework JavaScript"
                ]
            ),
            "ocr": AgentInfo(
                name="OCR Agent",
                description="Xử lý ảnh, nhận dạng văn bản, OCR và chuyển đổi tài liệu",
                capabilities=[
                    "Nhận dạng văn bản từ ảnh (OCR)",
                    "Xử lý và phân tích hình ảnh",
                    "Chuyển đổi tài liệu PDF thành text",
                    "Nhận dạng ký tự và bảng biểu",
                    "Extract text từ file ảnh",
                    "Scan và đọc nội dung tài liệu",
                    "Xử lý ảnh với nhiều định dạng"
                ],
                examples=[
                    "Xử lý ảnh này bằng OCR",
                    "Chuyển đổi tài liệu PDF thành text",
                    "Nhận dạng văn bản trong hình ảnh",
                    "Scan và đọc nội dung bảng biểu",
                    "Extract text từ file ảnh",
                    "Xử lý ảnh chứa công thức toán"
                ]
            ),
            "general": AgentInfo(
                name="General Agent",
                description="Trợ lý tổng quát, trả lời câu hỏi, tư vấn, hỗ trợ và lập trình",
                capabilities=[
                    "Trả lời câu hỏi tổng quát",
                    "Tư vấn và đưa ra gợi ý",
                    "Hướng dẫn và giải thích",
                    "So sánh và phân tích",
                    "Hỗ trợ lập trình và code",
                    "Debug và sửa lỗi",
                    "Viết function và tạo API",
                    "Phát triển phần mềm"
                ],
                examples=[
                    "Hôm nay là ngày gì?",
                    "Giải thích về machine learning",
                    "So sánh iPhone và Samsung",
                    "Hướng dẫn nấu phở",
                    "Làm sao viết function Python?",
                    "Cách debug lỗi JavaScript",
                    "Tạo API REST với Flask",
                    "Tư vấn chọn laptop"
                ]
            )
        }
    
    async def _get_llm_routing_decision(self, prompt: str) -> Dict[str, any]:
        """Use Groq LLM to make intelligent routing decision"""
        if not groq_client:
            return {
                "agent": "general",
                "confidence": 0.5,
                "reasoning": "GROQ không khả dụng, chọn general agent",
                "alternatives": []
            }
        
        try:
            # Create agent descriptions for LLM
            agents_desc = ""
            for agent_name, agent_info in self.agents.items():
                agents_desc += f"""
**{agent_info.name}** ({agent_name}):
- Mô tả: {agent_info.description}
- Khả năng: {', '.join(agent_info.capabilities[:3])}...
- Ví dụ: {', '.join(agent_info.examples[:2])}

"""
            
            routing_prompt = f"""Bạn là một hệ thống routing thông minh. Nhiệm vụ của bạn là chọn agent phù hợp nhất để xử lý câu hỏi của người dùng.

Các agent có sẵn:
{agents_desc}

Câu hỏi của người dùng: "{prompt}"

Hãy phân tích và trả lời theo định dạng JSON sau:
{{
    "agent": "tên_agent_được_chọn (math/research/ocr/general)",
    "confidence": số_từ_0_đến_1,
    "reasoning": "lý do chi tiết tại sao chọn agent này",
    "alternatives": [
        {{"agent": "tên_agent", "confidence": số_từ_0_đến_1, "reason": "lý do"}},
        ...
    ]
}}

Quy tắc chọn agent:
- math: Câu hỏi về toán học, phương trình, tính toán, thống kê
- research: Câu hỏi cần tìm kiếm thông tin mới, nghiên cứu, tin tức
- ocr: Yêu cầu xử lý ảnh, nhận dạng văn bản, OCR
- general: Câu hỏi tổng quát, lập trình, tư vấn, hướng dẫn

Hãy phân tích kỹ và chọn chính xác nhất có thể."""
            
            completion = groq_client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[{"role": "user", "content": routing_prompt}],
                temperature=0.1,  # Low temperature for consistent routing
                max_completion_tokens=500
            )
            
            response = completion.choices[0].message.content or "{}"
            
            # Clean response - remove any markdown formatting
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            # Fix escape characters
            response = response.replace("\\(", "(").replace("\\)", ")")
            
            print(f"LLM Response: {response}")  # Debug
            
            result = json.loads(response)
            
            # Validate and ensure required fields
            if "agent" not in result:
                result["agent"] = "general"
            if "confidence" not in result:
                result["confidence"] = 0.5
            if "reasoning" not in result:
                result["reasoning"] = "Không có lý do được cung cấp"
            if "alternatives" not in result:
                result["alternatives"] = []
            
            return result
            
        except Exception as e:
            print(f"LLM routing error: {e}")
            return {
                "agent": "general",
                "confidence": 0.3,
                "reasoning": f"Lỗi LLM routing: {str(e)}",
                "alternatives": []
            }
    
    async def route(self, prompt: str) -> RoutingDecision:
        """Main routing method using LLM"""
        # Get LLM routing decision
        llm_decision = await self._get_llm_routing_decision(prompt)
        
        # Validate agent exists
        chosen_agent = llm_decision["agent"]
        if chosen_agent not in self.agents:
            chosen_agent = "general"
            llm_decision["confidence"] = 0.3
            llm_decision["reasoning"] = f"Agent '{llm_decision['agent']}' không tồn tại, chọn general"
        
        # Format alternatives
        alternatives = []
        for alt in llm_decision.get("alternatives", []):
            if alt.get("agent") in self.agents:
                alternatives.append({
                    "agent": alt["agent"],
                    "confidence": alt.get("confidence", 0.0),
                    "reason": alt.get("reason", "Không có lý do")
                })
        
        return RoutingDecision(
            agent_type=chosen_agent,
            confidence=llm_decision["confidence"],
            reasoning=llm_decision["reasoning"],
            alternative_agents=alternatives
        )

# =================== Usage ===================
async def route_prompt(prompt: str) -> RoutingDecision:
    """Convenience function to route a prompt using LLM"""
    router = LLMRouter()
    return await router.route(prompt)

# =================== Testing ===================
async def test_llm_router():
    """Test function for LLM router"""
    test_prompts = [
        "Giải phương trình x^2 - 5x + 6 = 0",
        "Tìm hiểu về machine learning",
        "Xử lý ảnh này bằng OCR",
        "Làm sao viết function Python?",
        "Tin tức mới nhất về AI"
    ]
    
    router = LLMRouter()
    
    print("Testing LLM Router...")
    print("=" * 60)
    
    for prompt in test_prompts:
        decision = await router.route(prompt)
        print(f"Prompt: {prompt}")
        print(f"Agent: {decision.agent_type}")
        print(f"Confidence: {decision.confidence:.2f}")
        print(f"Reasoning: {decision.reasoning}")
        if decision.alternative_agents:
            print(f"Alternatives: {[alt['agent'] for alt in decision.alternative_agents]}")
        print("-" * 40)

if __name__ == "__main__":
    asyncio.run(test_llm_router())
