# utils/helpers.py
import re

def detect_language(text: str) -> str:
    """检测文本主要语言，返回 'zh' 或 'en'"""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_chars = len(text.strip())
    if total_chars == 0:
        return "unknown"
    ratio = chinese_chars / total_chars
    return "zh" if ratio > 0.3 else "en"