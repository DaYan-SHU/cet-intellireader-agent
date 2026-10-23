# config/settings.py
import os
import sys
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from langchain_deepseek import ChatDeepSeek

# 加载环境变量（兼容 PyInstaller 打包后的单文件模式）
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # 打包模式：先在解压目录找，再在 exe 同级目录找
    candidates = [
        Path(sys._MEIPASS) / '.env',
        Path(sys.executable).parent / '.env',
    ]
    env_file = None
    for p in candidates:
        if p.exists():
            env_file = str(p)
            break
else:
    # 开发模式：使用 find_dotenv 自动查找
    env_file = find_dotenv()

if env_file:
    load_dotenv(env_file, encoding='utf-8-sig', verbose=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
# 初始化LLM
llm = ChatDeepSeek(
    model="deepseek-chat",
    temperature=0.7,
    max_retries=2
)