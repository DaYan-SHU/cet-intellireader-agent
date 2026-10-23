# Streamlit 入口
# 启动方式：uv run streamlit run main.py
import os
import sys
from pathlib import Path

# 部分 Windows 环境的系统代理缺少协议前缀，会导致 httpx 请求 DeepSeek 时 TLS 报错；
# 仅在用户未自行配置 NO_PROXY 时，对 DeepSeek 域名走直连。
os.environ.setdefault("NO_PROXY", "api.deepseek.com")

# 将项目根目录添加到 Python 模块搜索路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from ui.streamlit_app import render

render()
