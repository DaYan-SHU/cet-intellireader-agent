# core/state.py
from typing import TypedDict

class AgentState(TypedDict):
    # 输入
    input_text: str
    level: str          # "四级" 或 "六级"
    genre: str          # "自动" / "议论文" / "说明文" / "叙事文"
    
    # 中间产物
    analysis: str
    analysis_summary: str  # 从 analysis 中提取的纯中文摘要（用于最终展示）
    article: str
    questions: str
    answers: str
    vocabulary: str
    critique: str
    
    # 控制流
    article_retries: int
    questions_retries: int
    max_retries: int
    
    # 联网搜索
    use_search: bool
    search_topic: str
    
    # 最终输出
    final_output: str

    # 输出控制
    include_vocab: bool