# 四六级出题 工作流（CET-IntelliReader Agent）

基于 LangGraph + DeepSeek 的四六级英语阅读智能命题系统。输入任意中/英文素材，自动生成符合四六级考试标准的英文文章、仔细阅读题、答案与解析、词汇表及分析摘要，并支持导出为 Word 文档。

# 简介

## 痛点直击

刷完真题就无题可刷？
模拟题质量参差不齐？
传统题库更新慢、风格死板、干扰项一眼识破？
CET-IntelliReader Agent 专为备考四六级的你而生。输入一段素材（或一个主题），AI 即刻生成一篇贴合考试难度的原创阅读文章，并配套 5 道高质量选择题（含主旨、细节、推理、词汇四大题型）+ 详细解析 + 高频词汇表。每一次练习，都是对考场的精准预演。

## 核心特性

特性	        说明
🧠 难度自适应	支持四级（400-450词）/ 六级（450-550词）双难度，自动匹配词汇与句法复杂度
📝 全题型覆盖	每篇生成 5 道标准选择题：主旨大意题、事实细节题、推理判断题、词汇理解题
🎯 智能干扰项	命题引擎生成迷惑性强的干扰项，杜绝一眼识破的送分题
🌐 联网素材	    集成 Tavily 搜索，输入主题即可自动检索并生成中文素材
✅ 双重质检	   文章与题目各经一轮 LLM 质检，不合格自动重试，保证输出质量
📚 词汇拓展	    自动提取 10-15 个四六级高频词汇，附中英文释义与例句
📄 一键导出	    结果一键导出为 Word 文档，方便打印与复习
🖥️ 双界面	    Streamlit Web UI（默认），并保留 Tkinter 桌面版

## 技术架构

### LangGraph 工作流（工程实现）

本项目基于 LangGraph 构建有状态多节点工作流，每个节点职责单一、可观测、可重试：

text
search（可选联网搜索）
→ analyze（素材分析与大纲提取）
→ gen\_article（文章生成）
→ check\_article（文章质检，不合格→重试）
→ gen\_questions（5题生成）
→ check\_questions（题目质检，不合格→重试）
→ gen\_answers（答案与中文解析）
→ gen\_vocabulary（高频词汇表）
→ finalize（整合最终输出）
关键设计：

条件路由：route\_after\_article\_check / route\_after\_questions\_check 根据质检结果决定是继续还是重试

状态管理：AgentState TypedDict 在节点间传递上下文（题目/答案/词汇/质量标记）

降级容错：无 Tavily Key 时搜索节点自动跳过；依赖缺失时搜索/导出功能优雅降级

## 技术栈

大模型：DeepSeek (deepseek-chat) via langchain-deepseek

编排框架：LangGraph（有状态工作流）+ LangChain Core

联网搜索：Tavily Search（可选）

文档导出：python-docx

前端界面：Streamlit（默认）；Tkinter（保留的桌面版入口）

打包分发：PyInstaller 单文件 exe

语言：Python 3.10+

## 环境配置

### 依赖安装（uv）

项目使用 uv 管理依赖与 Python 版本（`uv.lock` 锁定全部依赖版本）；同时导出 `requirements.txt` 供不使用 uv 的环境安装。分发清单与常见问题详见 [分发说明.md](分发说明.md)。

1. 安装 uv（已安装可跳过）：
   powershell
   pip install uv
   或参考官方脚本 <https://docs.astral.sh/uv/getting-started/installation/>
2. 在项目根目录执行，自动创建 .venv 并按 uv.lock 安装锁定版本依赖：
   powershell
   uv sync
3. 启动程序（Streamlit Web 界面）：
   powershell
   uv run streamlit run main.py

   或直接双击 `启动.bat`，它会自动执行 `uv sync` 并启动 Web 界面。

   如需使用旧版 Tkinter 桌面界面：
   powershell
   uv run main_tk.py

不使用 uv 时，也可以 `pip install -r requirements.txt` 后运行同样的命令。

uv 会读取 .python-version 自动使用 Python 3.10；本机没有时会自动下载受管版本，无需手动安装 Python。
分发前请保留 pyproject.toml、uv.lock、.python-version 三个文件，接收方只需执行 uv sync 即可得到完全一致的环境。

### .env 文件配置

在项目根目录创建 .env 文件，内容如下：

DEEPSEEK\_API\_KEY=你的DeepSeek密钥
TAVILY\_API\_KEY=你的Tavily密钥（可选）

### 配置说明

#### DeepSeek API 密钥

DEEPSEEK\_API\_KEY：必填，获取地址 <https://platform.deepseek.com/account/api>

#### Tavily API 密钥

可选，获取地址 <https://tavily.com> （不配置则联网搜索自动跳过，不影响其他功能）

## 界面说明

- Streamlit 版（默认）：`uv run streamlit run main.py`，单列极简布局，生成后在页面内预览并可下载 Word。
- Tkinter 桌面版（保留）：`uv run main_tk.py`，与旧版界面完全一致。

## 常见问题

### Q：生成失败提示 Connection error？

A：多为系统代理导致。入口脚本已默认把 `api.deepseek.com` 加入 NO_PROXY 走直连；如仍失败，可在启动前执行 `$env:NO_PROXY="*"` 后重试。

### Q：为什么没有系统「另存为」对话框？

A：Streamlit 版改为浏览器下载，点击「导出 Word」后由浏览器保存文件。

### Q：打包出的 exe 是哪个界面？

A：`exam_agent.spec` 的入口为 `main_tk.py`，打包产物仍是 Tkinter 桌面版。

