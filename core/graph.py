# core/graph.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from core.state import AgentState
from core.nodes import (
    search_node,
    analyze_text,
    generate_article,
    check_article_quality,
    route_after_article_check,
    generate_questions,
    check_questions_quality,
    route_after_questions_check,
    generate_answers,
    generate_vocabulary,
    finalize
)

def build_agent():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("search", search_node)
    workflow.add_node("analyze", analyze_text)
    workflow.add_node("gen_article", generate_article)
    workflow.add_node("check_article", check_article_quality)
    workflow.add_node("gen_questions", generate_questions)
    workflow.add_node("check_questions", check_questions_quality)
    workflow.add_node("gen_answers", generate_answers)
    workflow.add_node("gen_vocabulary", generate_vocabulary)
    workflow.add_node("finalize", finalize)

    workflow.set_entry_point("search")
    workflow.add_edge("search", "analyze")
    workflow.add_edge("analyze", "gen_article")
    workflow.add_edge("gen_article", "check_article")
    
    workflow.add_conditional_edges(
        "check_article",
        route_after_article_check,
        {
            "gen_article": "gen_article",
            "gen_questions": "gen_questions"
        }
    )
    
    workflow.add_edge("gen_questions", "check_questions")
    
    workflow.add_conditional_edges(
        "check_questions",
        route_after_questions_check,
        {
            "gen_questions": "gen_questions",
            "gen_answers": "gen_answers"
        }
    )
    
    workflow.add_edge("gen_answers", "gen_vocabulary")
    workflow.add_edge("gen_vocabulary", "finalize")
    workflow.add_edge("finalize", END)
    
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)

# 兼容旧名称
build_exam_agent = build_agent
