# core/nodes.py
from config.settings import llm
from core.state import AgentState
from utils.helpers import detect_language
from typing import Literal

# ============== 搜索节点（如果未安装 Tavily，则直接返回原文） ==============
def search_node(state: AgentState) -> dict:
    """节点：联网搜索生成文本（如果不可用则返回原文本）"""
    if state.get("use_search", False):
        topic = state.get("search_topic", "")
        if topic:
            try:
                from utils.search import search_and_summarize
                text = search_and_summarize(topic)
                if text:
                    return {"input_text": text}
            except ImportError:
                print("⚠️ 搜索模块未安装，跳过联网搜索")
            except Exception as e:
                print(f"搜索失败: {e}")
    return {"input_text": state.get("input_text", "")}


def _extract_chinese_summary(analysis: str) -> str:
    """从分析报告中提取纯中文理解摘要部分（健壮解析，兼容多种标记格式）"""
    separators = [
        "第二部分：英文大纲", "第二部分:英文大纲",
        "第二部分： 英文大纲",
        "【英文大纲】", "英文大纲",
    ]
    for sep in separators:
        if sep in analysis:
            chinese_part = analysis.split(sep)[0]
            prefixes = [
                "第一部分：中文理解摘要", "第一部分:中文理解摘要",
                "第一部分：中文摘要", "第一部分:中文摘要",
                "【中文理解摘要】", "【中文摘要】",
                "中文理解摘要", "中文摘要",
            ]
            stripped = chinese_part.strip().strip("-—").strip()
            for prefix in prefixes:
                if stripped.startswith(prefix):
                    stripped = stripped[len(prefix):].strip().strip("-—").strip()
                    break
            if stripped:
                return stripped

    # 兜底：未找到分隔符时，取前 150 字
    cleaned = analysis.strip().strip("-—").strip()
    return cleaned[:150] + ("..." if len(cleaned) > 150 else "")


def _extract_english_outline(analysis: str) -> str:
    """从分析报告中提取英文大纲部分"""
    separators = [
        "第二部分：英文大纲", "第二部分:英文大纲",
        "第二部分： 英文大纲", "【英文大纲】", "英文大纲",
    ]
    for sep in separators:
        if sep in analysis:
            parts = analysis.split(sep, 1)
            if len(parts) > 1:
                outline = parts[1].strip().strip("-—").strip()
                if outline:
                    return outline
    return ""


# ============== 节点1：分析文本 ==============
def analyze_text(state: AgentState) -> dict:
    """理解文本，提取大纲（支持中/英文）"""
    input_text = state['input_text']
    lang = detect_language(input_text)
    genre = state.get("genre", "自动")
    
    genre_instruction = {
        "议论文": "重点提取中心论点、分论点和论据。",
        "说明文": "重点提取核心概念、特征、分类或过程。",
        "叙事文": "重点提取人物、情节主线、时间地点和冲突。",
        "自动": "根据文本实际内容自动判断体裁并提取相应要素。"
    }.get(genre, "根据文本实际内容自动判断体裁并提取相应要素。")

    if lang == "en":
        prompt = f"""
你是一位资深英语教育专家和四六级命题专家。请阅读以下英文文本，提炼主题并生成英文文章大纲。

【输入文本】{input_text}
【体裁提示】{genre_instruction}

请严格按照以下两个部分输出，不要添加任何额外标题、解释或分隔线：

第一部分：中文理解摘要
（用50-80字中文概括文章核心内容）

第二部分：英文大纲
Title: （完整的英文标题）
Introduction: （用1-2个完整英文句子介绍文章背景和主题）
Body Paragraph 1: （用1个完整英文句子概括第一个主体段落的主旨）
Body Paragraph 2: （用1个完整英文句子概括第二个主体段落的主旨）
Body Paragraph 3 (if applicable): （如果原文有三个主体段落，用1个完整英文句子概括第三个主体段落；否则省略此项）
Conclusion: （用1个完整英文句子概括结论）

注意：每个部分都必须提供实质内容，不要只写短语或省略。
"""
    else:
        prompt = f"""
你是一位资深英语教育专家和四六级命题专家。请仔细阅读以下中文文本，理解后生成英文大纲。

【输入文本】{input_text}
【体裁提示】{genre_instruction}

请严格按照以下两个部分输出，不要添加任何额外标题、解释或分隔线：

第一部分：中文理解摘要
（用50-80字中文概括文章核心内容）

第二部分：英文大纲
Title: （完整的英文标题）
Introduction: （用1-2个完整英文句子介绍文章背景和主题）
Body Paragraph 1: （用1个完整英文句子概括第一个主体段落的主旨）
Body Paragraph 2: （用1个完整英文句子概括第二个主体段落的主旨）
Body Paragraph 3 (if applicable): （如果原文有三个主体段落，用1个完整英文句子概括第三个主体段落；否则省略此项）
Conclusion: （用1个完整英文句子概括结论）

注意：每个部分都必须提供实质内容，不要只写短语或省略。
"""
    
    analysis = llm.invoke(prompt).content
    summary = _extract_chinese_summary(analysis)
    outline = _extract_english_outline(analysis)
    return {
        "analysis": analysis,
        "analysis_summary": summary,
        "analysis_outline": outline,
        "article_retries": 0,
        "questions_retries": 0
    }


# ============== 节点2：生成文章 ==============
def generate_article(state: AgentState) -> dict:
    retries = state.get("article_retries", 0)
    critique = state.get("critique", "")
    refine = f"请根据以下意见修改：{critique}" if critique else "请直接生成高质量文章。"
    
    # 安全获取大纲，若不存在则从完整分析中提取
    outline = state.get('analysis_outline', '')
    if not outline:
        outline = _extract_english_outline(state.get('analysis', ''))
    
    prompt = f"""
    你是四六级命题专家。根据以下分析报告生成英文文章。

    【分析报告】{state['analysis']}
    【英文大纲】{outline}
    【修改指令】{refine}

    【要求】
    1. 级别:{state['level']}，词数:{"400-450" if '四级' in state['level'] else "450-550"}
    2. 严格基于大纲展开，段落分明，逻辑连贯
    3. 使用标准四六级考试风格，词汇地道

    只输出纯英文文章，不要包含中文解释。
    """
    article = llm.invoke(prompt).content
    return {"article": article, "article_retries": retries + 1, "critique": ""}


# ============== 节点3：质检文章 ==============
def check_article_quality(state: AgentState) -> dict:
    """质检文章质量"""
    prompt = f"""
    请审核以下文章是否符合{state['level']}标准。

    【文章】{state['article']}

    【审核标准】
    1. 词数是否达标（{"400-450" if '四级' in state['level'] else "450-550"}）？
    2. 主题清晰，与原文一致？
    3. 无语法错误或中式英语？
    4. 适合作为阅读理解材料？

    通过输出"PASS"，否则输出"FAIL: 具体建议"
    """
    result = llm.invoke(prompt).content.strip()
    if result.startswith("PASS"):
        return {"critique": "PASS"}
    return {"critique": result.replace("FAIL:", "").strip()}


# ============== 路由函数：文章质检后 ==============
def route_after_article_check(state: AgentState) -> Literal["gen_article", "gen_questions"]:
    if state.get("critique") == "PASS" or state.get("article_retries", 0) >= state.get("max_retries", 3):
        return "gen_questions"
    return "gen_article"


# ============== 节点4：生成题目 ==============
def generate_questions(state: AgentState) -> dict:
    retries = state.get("questions_retries", 0)
    critique = state.get("critique", "")
    refine = f"请根据以下意见修改：{critique}" if critique else "直接生成标准题目。"
    
    prompt = f"""
    请根据以下文章生成{state['level']}仔细阅读题。

    【文章】{state['article']}
    【修改指令】{refine}

    【要求】
    1. 只输出题目和选项，绝对不要重复文章内容或添加任何文章段落
    2. 5道四选一，编号46-50
    3. 含：主旨1道 + 细节2道 + 推理1道 + 词汇1道
    4. 干扰项有迷惑性
    5. 每道题后添加答题区域：______
    6. 输出格式严格如下（不要额外标题或说明）：
       46. 题目内容
           A) 选项A    B) 选项B    C) 选项C    D) 选项D
           ______
       47. ...

    只输出题目，不要附带答案。
    """
    questions = llm.invoke(prompt).content
    
    # 后处理：截取从第一个题号开始的部分，避免重复文章
    import re
    match = re.search(r'\n\s*46\.', questions)
    if match:
        questions = questions[match.start():].strip()
    
    return {"questions": questions, "questions_retries": retries + 1, "critique": ""}


# ============== 节点5：质检题目 ==============
def check_questions_quality(state: AgentState) -> dict:
    """质检题目"""
    prompt = f"""
    审核以下题目是否专业。

    【题目】{state['questions']}

    【标准】
    1. 恰好5道题？
    2. 包含主旨、细节、推理、词汇题？
    3. 每道题都有答题留白？
    4. 选项设置合理？

    通过输出"PASS"，否则输出"FAIL: 建议"
    """
    result = llm.invoke(prompt).content.strip()
    if result.startswith("PASS"):
        return {"critique": "PASS"}
    return {"critique": result.replace("FAIL:", "").strip()}


# ============== 路由函数：题目质检后 ==============
def route_after_questions_check(state: AgentState) -> Literal["gen_questions", "gen_answers"]:
    if state.get("critique") == "PASS" or state.get("questions_retries", 0) >= state.get("max_retries", 3):
        return "gen_answers"
    return "gen_questions"


# ============== 节点6：生成答案与解析 ==============
def generate_answers(state: AgentState) -> dict:
    """生成答案与解析"""
    prompt = f"""
    根据以下文章和题目生成答案与解析。

    【文章】{state['article']}
    【题目】{state['questions']}

    【要求】
    1. 每道题给出正确答案（如：46. A）
    2. 中文解析，说明正确和错误原因

    【格式】
    46. 答案：A
    解析：...
    47. 答案：B
    解析：...
    """
    answers = llm.invoke(prompt).content
    return {"answers": answers}


# ============== 节点7：生成词汇表 ==============
def generate_vocabulary(state: AgentState) -> dict:
    """生成词汇表（制表符分隔，便于Word转换）"""
    prompt = f"""
    从以下文章中提取10-15个重点词汇，生成词汇表。

    【文章】{state['article']}

    【要求】
    1. 选取对理解文章至关重要的四六级词汇
    2. 输出格式：每行一个词汇，英文、词性、中文释义之间用制表符（Tab键）分隔
    3. 不要添加任何表头、序号、竖线或其他装饰符号
    4. 按字母顺序排列
    5. 示例格式：
    abandon\tv.\t放弃；抛弃
    ability\tn.\t能力；才能
    """
    vocab = llm.invoke(prompt).content
    return {"vocabulary": vocab}


# ============== 节点8：整合输出 ==============
def finalize(state: AgentState) -> dict:
    """整合最终输出（根据 include_vocab 从源头控制是否包含词汇表）"""
    sections = [
        "========================================",
        f"       {state['level']} 阅读理解模拟题",
        "========================================",
        "",
        "【文章正文】",
        state['article'],
        "",
        "【题目部分】",
        state['questions'],
        "",
        "【答案与解析】",
        state.get('answers', ''),
    ]

    # 词汇表部分：仅在用户启用时包含
    if state.get("include_vocab", True):
        sections.extend([
            "",
            "【词汇表】",
            state.get('vocabulary', ''),
        ])

    # 中文摘要
    summary = state.get("analysis_summary", "") or _extract_chinese_summary(state.get("analysis", ""))
    sections.extend([
        "",
        "【素材理解摘要】",
        summary,
    ])

    # 英文大纲（新增展示）
    outline = state.get("analysis_outline", "") or _extract_english_outline(state.get("analysis", ""))
    if outline:
        sections.extend([
            "",
            "【英文大纲】",
            outline,
        ])

    output = "\n".join(sections)
    return {"final_output": output}
