try:
    from docx import Document
    from docx.shared import Inches, Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False


def _is_vocab_line(line: str) -> bool:
    """判断是否为词汇表的制表符分隔行（至少包含2个制表符，即3列）"""
    return line.count('\t') >= 2


def _add_vocab_table(doc, rows):
    """向文档添加词汇表表格（词汇 / 词性 / 释义）"""
    table = doc.add_table(rows=1, cols=3)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # 表头
    headers = ['词汇', '词性', '释义']
    for idx, text in enumerate(headers):
        cell = table.rows[0].cells[idx]
        cell.text = text
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.font.bold = True

    # 数据行
    for row in rows:
        cells = table.add_row().cells
        for idx, text in enumerate(row):
            cells[idx].text = text

    # 表格后留一个空段落，避免与后续内容粘连
    doc.add_paragraph('')


def export_to_word(content: str, file_path: str) -> bool:
    """导出最终生成内容为 Word 文档（不含运行日志）

    解析规则：
    - 以 === 开头的行视为分隔线，跳过
    - 以【...】开头的行作为二级章节标题
    - 词汇表区域内的制表符分隔行转为 Word 表格
    - 题号行（46.-50.）缩进显示
    - 其他行作为普通段落
    """
    if not HAS_DOCX:
        return False

    try:
        lines = content.split('\n')

        # 优先从首个 === 标题块中提取真实标题（保留四级/六级信息）
        doc_title = "四六级阅读理解模拟题"
        for idx, line in enumerate(lines):
            if line.strip().startswith('='):
                # 标题块：找到下一个 === 行，中间的非空行即标题
                for j in range(idx + 1, len(lines)):
                    if lines[j].strip().startswith('='):
                        break
                    candidate = lines[j].strip()
                    if candidate:
                        doc_title = candidate
                        break
                break

        doc = Document()
        title = doc.add_heading(doc_title, level=1)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        i = 0
        in_vocab = False
        vocab_rows = []
        in_title_block = False  # === 包围的文档标题块，整体跳过

        while i < len(lines):
            stripped = lines[i].strip()

            if not stripped:
                i += 1
                continue

            # 分隔线 ===：切换标题块状态，标题块整体跳过（一级标题已由 add_heading 处理）
            if stripped.startswith('='):
                in_title_block = not in_title_block
                i += 1
                continue

            if in_title_block:
                i += 1
                continue

            # 章节标题 【...】
            if stripped.startswith('【'):
                # 先 flush 之前累积的词汇表
                if in_vocab and vocab_rows:
                    _add_vocab_table(doc, vocab_rows)
                    vocab_rows = []
                in_vocab = False

                heading = stripped.strip('【】').strip()
                doc.add_heading(heading, level=2)

                if '词汇表' in heading:
                    in_vocab = True
                i += 1
                continue

            # 词汇表区域：收集制表符分隔行
            if in_vocab and _is_vocab_line(stripped):
                parts = stripped.split('\t')
                # 补齐到3列
                while len(parts) < 3:
                    parts.append('')
                vocab_rows.append(parts[:3])
                i += 1
                continue
            elif in_vocab:
                # 词汇表区域内遇到非制表符行，结束词汇表收集
                if vocab_rows:
                    _add_vocab_table(doc, vocab_rows)
                    vocab_rows = []
                in_vocab = False
                # 不跳过当前行，继续走普通段落逻辑
                continue

            # 题号行 46.-50.，缩进显示
            if stripped.startswith(('46.', '47.', '48.', '49.', '50.')):
                p = doc.add_paragraph(stripped)
                p.paragraph_format.left_indent = Inches(0.3)
            else:
                doc.add_paragraph(stripped)

            i += 1

        # 处理文档末尾累积的词汇表
        if in_vocab and vocab_rows:
            _add_vocab_table(doc, vocab_rows)

        doc.save(file_path)
        return True
    except Exception:
        return False
