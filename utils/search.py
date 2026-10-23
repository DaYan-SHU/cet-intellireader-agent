# utils/search.py
from config.settings import TAVILY_API_KEY, llm

# 尝试导入 Tavily 搜索工具
try:
    from langchain_tavily import TavilySearch
    SEARCH_AVAILABLE = True
except ImportError:
    SEARCH_AVAILABLE = False

def get_search_tool():
    """获取搜索工具实例"""
    if not SEARCH_AVAILABLE:
        return None
    try:
        return TavilySearch(api_key=TAVILY_API_KEY, max_results=3)
    except Exception:
        return None

def search_and_summarize(topic: str) -> str:
    """根据主题搜索并生成中文摘要"""
    if not SEARCH_AVAILABLE or not TAVILY_API_KEY:
        return ""
    
    tool = get_search_tool()
    if not tool:
        return ""
    
    try:
        results = tool.invoke(topic)
        prompt = f"""
        请根据以下搜索结果，整理出一篇适合作为四六级阅读理解材料的中文文本。

        【搜索主题】{topic}
        【搜索结果】{results}

        【要求】
        1. 整合关键信息，生成 400-600 字的中文文本
        2. 结构清晰，适合作为考试阅读材料
        3. 文本内容基于四六级大纲展开，段落分明，逻辑连贯
        """
        return llm.invoke(prompt).content
    except Exception as e:
        print(f"搜索失败: {e}")
        return ""