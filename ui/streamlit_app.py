# ui/streamlit_app.py
"""四六级出题 Agent 的 Streamlit 界面。

本文件只负责展示与交互编排，业务链路（LangGraph 工作流、节点逻辑、Word 导出）
全部复用 core/ 与 utils/ 中的现有实现，不在此重复业务代码。
"""

import os
import tempfile
import traceback
from pathlib import Path

import streamlit as st

from core.graph import build_agent
from ui.theme import apply_theme
from utils.export import HAS_DOCX, export_to_word

DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

# 节点进度与中文标签（与旧 Tk 界面保持一致）
NODE_PROGRESS = {
    "search": 8,
    "analyze": 18,
    "gen_article": 32,
    "check_article": 42,
    "gen_questions": 56,
    "check_questions": 66,
    "gen_answers": 76,
    "gen_vocabulary": 86,
    "finalize": 96,
}

NODE_LABELS = {
    "search": "联网搜索",
    "analyze": "素材分析",
    "gen_article": "生成文章",
    "check_article": "文章质检",
    "gen_questions": "生成题目",
    "check_questions": "题目质检",
    "gen_answers": "生成答案解析",
    "gen_vocabulary": "生成词汇表",
    "finalize": "整合输出",
}


# ============== 状态初始化 ==============
def _init_state() -> None:
    """初始化会话状态，避免 rerun 后结果丢失。"""
    defaults = {
        "final_output": "",
        "logs": [],
        "status": "idle",  # idle / done / error
        "error": "",
        "traceback": "",
        "article_retries": 0,
        "questions_retries": 0,
        "last_level": "六级",
        "last_run_label": "",
        "_docx_for": None,
        "_docx_bytes": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    # 每个浏览器会话持有独立的 agent，避免 MemorySaver 状态互相污染
    if "agent" not in st.session_state:
        st.session_state["agent"] = build_agent()


# ============== 表单 ==============
def _render_form() -> dict:
    with st.form("generate_form"):
        text = st.text_area(
            "素材文本",
            height=220,
            placeholder="粘贴中/英文文章或段落，支持多行；也可勾选联网搜索后只填主题",
        )
        use_search = st.checkbox("启用联网搜索", value=False)
        search_topic = st.text_input(
            "搜索主题",
            placeholder="如：人工智能发展（需配置 TAVILY_API_KEY）",
        )

        col_level, col_genre = st.columns(2)
        level = col_level.selectbox("考试级别", ["四级", "六级"], index=1)
        genre = col_genre.selectbox(
            "文章体裁", ["自动", "议论文", "说明文", "叙事文"], index=0
        )

        max_retries = st.number_input(
            "最大重试次数", min_value=0, max_value=5, value=3, step=1
        )
        include_vocab = st.checkbox("生成词汇表", value=True)

        submitted = st.form_submit_button(
            "开始生成", type="primary", use_container_width=True
        )

    return {
        "text": text,
        "use_search": use_search,
        "search_topic": search_topic,
        "level": level,
        "genre": genre,
        "max_retries": int(max_retries),
        "include_vocab": include_vocab,
        "submitted": submitted,
    }


def _handle_submit(
    text: str,
    level: str,
    genre: str,
    max_retries: int,
    use_search: bool,
    search_topic: str,
    include_vocab: bool,
) -> None:
    text = (text or "").strip()
    search_topic = (search_topic or "").strip()

    if not text and not (use_search and search_topic):
        st.error("请输入素材文本，或勾选「启用联网搜索」并填写搜索主题")
        return

    _execute(text, level, genre, max_retries, use_search, search_topic, include_vocab)


# ============== 执行工作流 ==============
def _execute(
    text: str,
    level: str,
    genre: str,
    max_retries: int,
    use_search: bool,
    search_topic: str,
    include_vocab: bool,
) -> None:
    agent = st.session_state["agent"]

    initial_state = {
        "input_text": text,
        "level": level,
        "genre": genre,
        "analysis": "",
        "analysis_summary": "",
        "article": "",
        "questions": "",
        "answers": "",
        "vocabulary": "",
        "critique": "",
        "article_retries": 0,
        "questions_retries": 0,
        "max_retries": max_retries,
        "use_search": use_search,
        "search_topic": search_topic,
        "final_output": "",
        "include_vocab": include_vocab,
    }
    config = {"configurable": {"thread_id": "ui_session"}}

    logs = [
        "正在启动四六级出题 Agent",
        f"级别: {level}  |  体裁: {genre}  |  最大重试: {max_retries} 次",
    ]
    if use_search:
        logs.append(f"联网搜索主题: {search_topic}")
    logs.append("-" * 40)

    # 新一轮生成前清空旧结果，避免失败时仍展示上一次输出
    st.session_state.update(
        {"final_output": "", "status": "idle", "error": "", "traceback": ""}
    )

    progress = st.progress(0, text="准备中…")
    log_box = st.expander("运行日志", expanded=True)
    log_slot = log_box.empty()
    log_slot.text("\n".join(logs))

    final_state = dict(initial_state)

    try:
        stream_api_failed = False
        try:
            for event in agent.stream(initial_state, config=config):
                for node_name, state_update in event.items():
                    if state_update:
                        final_state.update(state_update)
                    pct = NODE_PROGRESS.get(node_name)
                    if pct:
                        label = NODE_LABELS.get(node_name, node_name)
                        logs.append(f"✓ {label} 完成 ({pct}%)")
                        progress.progress(pct, text=f"{label} 完成")
                        log_slot.text("\n".join(logs))
        except (AttributeError, TypeError) as api_err:
            # 仅当 stream 方法不存在或签名不兼容时回退；真实业务错误继续向上抛出
            stream_api_failed = True
            logs.append(f"流式进度不可用，切换为标准模式: {api_err}")
            log_slot.text("\n".join(logs))

        if stream_api_failed:
            final_state = agent.invoke(initial_state, config=config)

        output = final_state.get("final_output", "")
        logs.append("生成完成")
        st.session_state.update(
            {
                "final_output": output,
                "logs": logs,
                "status": "done",
                "error": "",
                "traceback": "",
                "article_retries": final_state.get("article_retries", 0),
                "questions_retries": final_state.get("questions_retries", 0),
                "last_level": level,
                "last_run_label": (
                    f"{level} · 体裁 {genre} · 最大重试 {max_retries} 次"
                ),
                "_docx_for": None,
                "_docx_bytes": None,
            }
        )
        progress.progress(100, text="生成完成")
        st.rerun()

    except Exception as exc:  # noqa: BLE001 - 界面需要展示任意失败原因
        logs.extend(["", f"发生错误: {exc}"])
        st.session_state.update(
            {
                "logs": logs,
                "status": "error",
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        st.rerun()


# ============== 结果展示 ==============
def _to_docx_bytes(content: str) -> bytes | None:
    """调用现有导出逻辑写入临时文件，再读成 bytes 供浏览器下载。"""
    if not HAS_DOCX:
        return None

    fd, path = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    try:
        if not export_to_word(content, path):
            return None
        return Path(path).read_bytes()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _ensure_docx(content: str) -> bytes | None:
    """按内容缓存 Word 字节，避免每次 rerun 都重新生成。"""
    if st.session_state.get("_docx_for") == content:
        return st.session_state.get("_docx_bytes")

    data = _to_docx_bytes(content)
    st.session_state["_docx_for"] = content
    st.session_state["_docx_bytes"] = data
    return data


def _escape_cell(text: str) -> str:
    """转义 Markdown 表格中的竖线。"""
    return text.strip().replace("|", "\\|")


def _content_to_markdown(content: str) -> str:
    """把最终输出转成 Markdown 预览。

    解析规则与 utils/export.py 保持一致：
    === 包围的标题块作为页面标题；【...】作为章节标题；词汇表区域的制表符行转表格。
    与 Word 导出不同的是这里只做展示，不改变原始内容。
    """
    lines = content.split("\n")

    # 取首个 === 标题块中的标题
    title = ""
    for idx, line in enumerate(lines):
        if line.strip().startswith("="):
            for j in range(idx + 1, len(lines)):
                if lines[j].strip().startswith("="):
                    break
                if lines[j].strip():
                    title = lines[j].strip()
                    break
            break

    out = [f"### {title}", ""] if title else []
    vocab_rows = []
    in_vocab = False
    in_title_block = False

    def flush_vocab() -> None:
        if not vocab_rows:
            return
        out.append("| 词汇 | 词性 | 释义 |")
        out.append("| --- | --- | --- |")
        for row in vocab_rows:
            out.append("| " + " | ".join(_escape_cell(cell) for cell in row) + " |")
        out.append("")
        vocab_rows.clear()

    for line in lines:
        stripped = line.strip()

        # 分隔线 ===：标题块整体跳过（标题已单独渲染）
        if stripped.startswith("="):
            in_title_block = not in_title_block
            continue

        if in_title_block:
            continue

        if not stripped:
            out.append("")
            continue

        # 章节标题【...】
        if stripped.startswith("【"):
            flush_vocab()
            heading = stripped.strip("【】").strip()
            out.append(f"#### {heading}")
            out.append("")
            in_vocab = "词汇表" in heading
            continue

        # 词汇表：制表符分隔行
        if in_vocab and stripped.count("\t") >= 2:
            parts = stripped.split("\t")
            while len(parts) < 3:
                parts.append("")
            vocab_rows.append(parts[:3])
            continue

        if in_vocab:
            flush_vocab()
            in_vocab = False

        # 普通正文行保留换行（行尾两个空格 = Markdown 硬换行）
        out.append(f"{stripped}  ")

    flush_vocab()
    return "\n".join(out)


def _render_export(content: str) -> None:
    if not HAS_DOCX:
        st.warning("未安装 python-docx，无法导出 Word")
        return

    data = _ensure_docx(content)
    if not data:
        st.warning("Word 文档生成失败")
        return

    st.download_button(
        "导出 Word",
        data=data,
        file_name=f"{st.session_state.last_level}阅读理解模拟题.docx",
        mime=DOCX_MIME,
    )


def _render_status() -> None:
    if st.session_state.status == "error":
        st.divider()
        st.error(f"生成失败：{st.session_state.error}")
        if st.session_state.traceback:
            with st.expander("错误详情"):
                st.code(st.session_state.traceback, language="text")

    output = st.session_state.final_output
    if not output:
        return

    st.divider()
    st.subheader("生成结果")
    if st.session_state.last_run_label:
        st.caption(st.session_state.last_run_label)

    rich = st.toggle("富文本预览", value=False, key="result_rich")

    if rich:
        with st.container(height=520, border=True):
            st.markdown(_content_to_markdown(output))
    else:
        st.text_area(
            "生成内容",
            value=output,
            height=520,
            disabled=True,
            label_visibility="collapsed",
        )

    _render_export(output)

    st.caption(
        f"文章重试 {st.session_state.article_retries} 次 · "
        f"题目重试 {st.session_state.questions_retries} 次"
    )

    if st.session_state.logs:
        with st.expander("运行日志"):
            st.text("\n".join(st.session_state.logs))


# ============== 页面入口 ==============
def render() -> None:
    st.set_page_config(page_title="四六级出题 Agent", layout="centered")
    apply_theme()
    _init_state()

    st.title("四六级出题 Agent")
    st.caption(
        "输入中/英文素材，生成四级或六级阅读理解模拟题、答案解析与词汇表"
    )

    form_data = _render_form()
    if form_data["submitted"]:
        _handle_submit(
            text=form_data["text"],
            level=form_data["level"],
            genre=form_data["genre"],
            max_retries=form_data["max_retries"],
            use_search=form_data["use_search"],
            search_topic=form_data["search_topic"],
            include_vocab=form_data["include_vocab"],
        )

    _render_status()
