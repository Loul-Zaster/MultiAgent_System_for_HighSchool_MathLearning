import os
import json
import asyncio
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import numpy as np
from sentence_transformers import SentenceTransformer
from groq import Groq

# =================== Configuration ===================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client: Optional[Groq] = None
if GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        print(f"⚠️ Failed to initialize Groq client in semantic router: {e}")
        groq_client = None
else:
    groq_client = None

# =================== Data Structures ===================
@dataclass
class AgentProfile:
    name: str
    description: str
    keywords: List[str]
    examples: List[str]
    capabilities: List[str]
    embedding: Optional[np.ndarray] = None

@dataclass
class RoutingDecision:
    agent_type: str
    confidence: float
    reasoning: str
    context_analysis: Dict[str, any]

# =================== Semantic Router ===================
class SemanticRouter:
    def __init__(self):
        self.model = None
        self.agent_profiles = self._initialize_agent_profiles()
        self._load_embedding_model()
        self._compute_embeddings()
    
    def _load_embedding_model(self):
        """Load sentence transformer model for semantic similarity"""
        try:
            # Use a lightweight multilingual model
            self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        except Exception as e:
            print(f"⚠️ Không thể load embedding model: {e}")
            self.model = None
    
    def _initialize_agent_profiles(self) -> Dict[str, AgentProfile]:
        """Define comprehensive agent profiles with examples and capabilities"""
        return {
            "math": AgentProfile(
                name="Math Agent",
                description="Chuyên giải toán, phương trình, tính toán, phân tích số liệu",
                keywords=[
                    "giải", "phương trình", "toán", "tính", "tính toán", "x^", "=", "công thức",
                    "đại số", "hình học", "giải tích", "thống kê", "xác suất", "ma trận",
                    "đạo hàm", "tích phân", "logarit", "sin", "cos", "tan", "căn bậc",
                    "bất phương trình", "hệ phương trình", "đồ thị", "hàm số"
                ],
                examples=[
                    "Giải phương trình x^2 - 5x + 6 = 0",
                    "Tính đạo hàm của hàm f(x) = x^3 + 2x^2 - 5x + 1",
                    "Tìm nghiệm của hệ phương trình tuyến tính",
                    "Vẽ đồ thị hàm số y = sin(x)",
                    "Tính xác suất của biến cố ngẫu nhiên"
                ],
                capabilities=[
                    "Giải phương trình đại số", "Tính toán vi phân", "Phân tích thống kê",
                    "Vẽ đồ thị hàm số", "Giải hệ phương trình", "Tính xác suất"
                ]
            ),
            "research": AgentProfile(
                name="Research Agent", 
                description="Nghiên cứu, tìm kiếm thông tin, tin tức, phân tích dữ liệu",
                keywords=[
                    "nghiên cứu", "tìm hiểu", "thông tin", "tin tức", "news", "tìm kiếm",
                    "phân tích", "báo cáo", "báo chí", "cập nhật", "mới nhất", "xu hướng",
                    "thị trường", "kinh tế", "chính trị", "công nghệ", "khoa học", "y tế",
                    "giáo dục", "môi trường", "năng lượng", "tài chính", "đầu tư"
                ],
                examples=[
                    "Tin tức mới nhất về AI tuần này",
                    "Phân tích xu hướng thị trường chứng khoán",
                    "Tìm hiểu về công nghệ blockchain",
                    "Báo cáo về tình hình kinh tế Việt Nam",
                    "Nghiên cứu về biến đổi khí hậu"
                ],
                capabilities=[
                    "Tìm kiếm thông tin realtime", "Phân tích xu hướng", "Tổng hợp báo cáo",
                    "Cập nhật tin tức", "Nghiên cứu thị trường", "Phân tích dữ liệu"
                ]
            ),
            "ocr": AgentProfile(
                name="OCR Agent",
                description="Xử lý ảnh, OCR, nhận dạng văn bản, scan tài liệu",
                keywords=[
                    "ocr", "ảnh", "hình", "image", "scan", "nhận dạng", "văn bản",
                    "tài liệu", "pdf", "jpg", "png", "bmp", "tiff", "chuyển đổi",
                    "text", "extract", "đọc", "chữ", "ký tự", "bảng", "biểu đồ"
                ],
                examples=[
                    "Xử lý ảnh này bằng OCR",
                    "Chuyển đổi tài liệu PDF thành text",
                    "Nhận dạng văn bản trong hình ảnh",
                    "Scan và đọc nội dung bảng biểu",
                    "Extract text từ file ảnh"
                ],
                capabilities=[
                    "OCR văn bản", "Xử lý ảnh", "Nhận dạng ký tự", "Chuyển đổi tài liệu",
                    "Extract text", "Scan tài liệu", "Nhận dạng bảng biểu"
                ]
            ),
            "general": AgentProfile(
                name="General Agent",
                description="Trợ lý tổng quát, trả lời câu hỏi, tư vấn, hỗ trợ, lập trình",
                keywords=[
                    "hỏi", "giúp", "tư vấn", "hướng dẫn", "cách", "làm sao", "tại sao",
                    "là gì", "như thế nào", "khi nào", "ở đâu", "ai", "cái gì", "tại sao",
                    "giải thích", "mô tả", "so sánh", "phân biệt", "ưu nhược điểm",
                    "code", "lập trình", "programming", "python", "javascript", "java",
                    "function", "class", "variable", "debug", "bug", "sửa lỗi",
                    "viết", "tạo", "xây dựng", "phát triển", "thiết kế"
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
                ],
                capabilities=[
                    "Trả lời câu hỏi", "Tư vấn", "Hướng dẫn", "Giải thích", "So sánh",
                    "Phân tích", "Đưa ra gợi ý", "Hỗ trợ tổng quát", "Lập trình", "Code",
                    "Debug", "Viết function", "Tạo API", "Phát triển phần mềm"
                ]
            )
        }
    
    def _compute_embeddings(self):
        """Compute embeddings for all agent profiles"""
        if not self.model:
            return
        
        for agent_name, profile in self.agent_profiles.items():
            # Combine description, keywords, and examples for embedding
            text = f"{profile.description} {' '.join(profile.keywords)} {' '.join(profile.examples)}"
            profile.embedding = self.model.encode(text)
    
    async def _analyze_context_with_ai(self, prompt: str) -> Dict[str, any]:
        """Use Groq to analyze context and extract structured information"""
        if not groq_client:
            return {"intent": "unknown", "domain": "general", "complexity": "medium"}
        
        try:
            analysis_prompt = f"""
Phân tích câu hỏi sau và trả lời dạng JSON:
{{
    "intent": "mục đích chính (solve/research/process/help/learn)",
    "domain": "lĩnh vực (math/science/tech/business/health/education/general)",
    "complexity": "độ phức tạp (simple/medium/complex)",
    "requires_tools": ["danh sách công cụ cần thiết"],
    "urgency": "mức độ khẩn cấp (low/medium/high)",
    "language": "ngôn ngữ chính (vi/en/mixed)"
}}

Câu hỏi: "{prompt}"
"""
            
            completion = groq_client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[{"role": "user", "content": analysis_prompt}],
                temperature=0.3,
                max_completion_tokens=200
            )
            
            response = completion.choices[0].message.content or "{}"
            return json.loads(response)
        except Exception as e:
            return {"intent": "unknown", "domain": "general", "complexity": "medium", "error": str(e)}
    
    def _calculate_semantic_similarity(self, prompt: str, agent_profile: AgentProfile) -> float:
        """Calculate semantic similarity between prompt and agent profile"""
        if not self.model or agent_profile.embedding is None:
            # Fallback to keyword matching
            prompt_lower = prompt.lower()
            matches = sum(1 for keyword in agent_profile.keywords if keyword in prompt_lower)
            return matches / len(agent_profile.keywords) if agent_profile.keywords else 0
        
        try:
            prompt_embedding = self.model.encode(prompt)
            similarity = np.dot(prompt_embedding, agent_profile.embedding) / (
                np.linalg.norm(prompt_embedding) * np.linalg.norm(agent_profile.embedding)
            )
            return float(similarity)
        except Exception:
            return 0.0
    
    def _calculate_keyword_score(self, prompt: str, agent_profile: AgentProfile) -> float:
        """Calculate keyword-based matching score"""
        prompt_lower = prompt.lower()
        matches = sum(1 for keyword in agent_profile.keywords if keyword in prompt_lower)
        return matches / len(agent_profile.keywords) if agent_profile.keywords else 0
    
    def _calculate_context_score(self, context: Dict[str, any], agent_name: str) -> float:
        """Calculate score based on context analysis"""
        score = 0.0
        
        # Intent matching
        intent = context.get("intent", "")
        if agent_name == "math" and intent in ["solve", "calculate"]:
            score += 0.3
        elif agent_name == "research" and intent in ["research", "learn"]:
            score += 0.3
        elif agent_name == "ocr" and intent in ["process"]:
            score += 0.3
        elif agent_name == "code" and intent in ["solve", "create"]:
            score += 0.3
        elif agent_name == "general" and intent in ["help", "learn"]:
            score += 0.3
        
        # Domain matching
        domain = context.get("domain", "")
        if agent_name == "math" and domain in ["math", "science"]:
            score += 0.2
        elif agent_name == "research" and domain in ["business", "tech", "science"]:
            score += 0.2
        elif agent_name == "code" and domain in ["tech"]:
            score += 0.2
        elif agent_name == "general":
            score += 0.1  # General gets baseline score
        
        # Complexity consideration
        complexity = context.get("complexity", "medium")
        if complexity == "complex" and agent_name in ["math", "code"]:
            score += 0.1
        
        return min(score, 1.0)
    
    async def route(self, prompt: str) -> RoutingDecision:
        """Main routing method with multi-layered analysis"""
        # Step 1: Context analysis with AI
        context = await self._analyze_context_with_ai(prompt)
        
        # Step 2: Calculate scores for each agent
        agent_scores = {}
        for agent_name, profile in self.agent_profiles.items():
            semantic_score = self._calculate_semantic_similarity(prompt, profile)
            keyword_score = self._calculate_keyword_score(prompt, profile)
            context_score = self._calculate_context_score(context, agent_name)
            
            # Weighted combination
            final_score = (
                semantic_score * 0.4 +
                keyword_score * 0.3 +
                context_score * 0.3
            )
            
            agent_scores[agent_name] = {
                "score": final_score,
                "semantic": semantic_score,
                "keyword": keyword_score,
                "context": context_score
            }
        
        # Step 3: Select best agent
        best_agent = max(agent_scores.items(), key=lambda x: x[1]["score"])
        agent_name, scores = best_agent
        
        # Step 4: Generate reasoning
        reasoning_parts = []
        if scores["semantic"] > 0.7:
            reasoning_parts.append("Tương đồng ngữ nghĩa cao")
        if scores["keyword"] > 0.3:
            reasoning_parts.append("Khớp từ khóa chuyên môn")
        if scores["context"] > 0.5:
            reasoning_parts.append("Phù hợp với ngữ cảnh")
        
        reasoning = "; ".join(reasoning_parts) if reasoning_parts else "Phân tích tổng hợp"
        
        return RoutingDecision(
            agent_type=agent_name,
            confidence=scores["score"],
            reasoning=reasoning,
            context_analysis={
                "scores": agent_scores,
                "context": context,
                "best_match": agent_name
            }
        )

# =================== Usage ===================
async def route_prompt(prompt: str) -> RoutingDecision:
    """Convenience function to route a prompt"""
    router = SemanticRouter()
    return await router.route(prompt)
