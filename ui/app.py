# ui/app.py
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import queue
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.graph import build_agent
from utils.export import export_to_word, HAS_DOCX

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

class ExamAgentUI:
    def __init__(self, root):
        self.root = root
        self.root.title("四六级出题 Agent")
        self.root.geometry("1000x850")
        self.root.resizable(True, True)
        
        self.progress_queue = queue.Queue()
        self.running = False
        self.agent = build_agent()
        # 专门保存最终生成内容，用于导出 Word（不含运行日志）
        self.final_output = ""

        # 样式
        style = ttk.Style()
        style.configure("TButton", padding=6, font=("黑体", 10))
        style.configure("TLabel", font=("黑体", 10))
        style.configure("TCombobox", font=("黑体", 10))

        # 主框架
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. 输入文本区域
        ttk.Label(main_frame, text="请输入文本(支持中/英文，多行):", font=("黑体", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0,5))
        self.text_input = scrolledtext.ScrolledText(main_frame, height=8, wrap=tk.WORD, font=("宋体", 10))
        self.text_input.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=(0,5))

        # 2. 搜索设置
        search_frame = ttk.Frame(main_frame)
        search_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=2)
        self.use_search_var = tk.BooleanVar(value=False)
        search_check = ttk.Checkbutton(search_frame, text="启用联网搜索(输入主题)", variable=self.use_search_var)
        search_check.pack(side=tk.LEFT, padx=(0,10))
        self.search_topic_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_topic_var, width=30)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(search_frame, text="(需要TAVILY_API_KEY)", font=("黑体", 10), foreground="black").pack(side=tk.LEFT, padx=(5,0))
        # 3. 参数设置
        param_frame = ttk.Frame(main_frame)
        param_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=5)

        ttk.Label(param_frame, text="考试级别:", font=("黑体", 10)).pack(side=tk.LEFT, padx=(0,5))
        self.level_var = tk.StringVar(value="六级")
        level_combo = ttk.Combobox(param_frame, textvariable=self.level_var, values=["四级", "六级"], state="readonly", width=6)
        level_combo.pack(side=tk.LEFT, padx=(0,15))

        ttk.Label(param_frame, text="文章体裁:", font=("黑体", 10)).pack(side=tk.LEFT, padx=(0,5))
        self.genre_var = tk.StringVar(value="自动")
        genre_combo = ttk.Combobox(param_frame, textvariable=self.genre_var, values=["自动", "议论文", "说明文", "叙事文"], state="readonly", width=8)
        genre_combo.pack(side=tk.LEFT, padx=(0,15))

        ttk.Label(param_frame, text="重试次数(0-5):").pack(side=tk.LEFT, padx=(0,5))
        self.retries_var = tk.StringVar(value="3")
        retries_entry = ttk.Entry(param_frame, textvariable=self.retries_var, width=4)
        retries_entry.pack(side=tk.LEFT, padx=(0,15))

        ttk.Label(param_frame, text="词汇表:", font=("黑体", 10)).pack(side=tk.LEFT, padx=(0,5))
        self.vocab_var = tk.BooleanVar(value=True)
        vocab_check = ttk.Checkbutton(param_frame, variable=self.vocab_var)
        vocab_check.pack(side=tk.LEFT)

        # 4. 按钮和进度条
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=5)

        self.generate_btn = ttk.Button(btn_frame, text="开始生成", command=self.start_generation, width=12)
        self.generate_btn.pack(side=tk.LEFT, padx=(0,10))

        self.export_btn = ttk.Button(btn_frame, text="导出 Word", command=self.export_word, width=12)
        self.export_btn.pack(side=tk.LEFT, padx=(0,10))

        self.progress = ttk.Progressbar(btn_frame, orient='horizontal', length=300, mode='determinate', maximum=100)
        self.progress.pack(side=tk.LEFT, padx=(10,10), fill=tk.X, expand=True)

        self.status_label = ttk.Label(btn_frame, text="就绪", font=("黑体", 9), foreground="gray")
        self.status_label.pack(side=tk.RIGHT)

        # 5. 输出结果
        ttk.Label(main_frame, text="生成结果:", font=("黑体", 11, "bold")).grid(row=5, column=0, sticky="w", pady=(10,5))
        self.output_text = scrolledtext.ScrolledText(main_frame, height=20, wrap=tk.WORD, font=("黑体", 10), state=tk.DISABLED)
        self.output_text.grid(row=6, column=0, columnspan=3, sticky="nsew", pady=(0,5))

        # 网格权重
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(6, weight=3)

        self.update_progress()

    def log_output(self, message):
        self.output_text.config(state=tk.NORMAL)
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def clear_output(self):
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state=tk.DISABLED)

    def set_status(self, text, color="gray"):
        self.status_label.config(text=text, foreground=color)
        self.root.update_idletasks()

    def update_progress(self):
        try:
            value = self.progress_queue.get_nowait()
            if value == -1:
                self.progress['value'] = 0
            else:
                self.progress['value'] = value
        except queue.Empty:
            pass
        self.root.after(200, self.update_progress)

    def start_generation(self):
        if self.running:
            messagebox.showwarning("提示", "生成任务正在进行中，请稍候...")
            return

        text = self.text_input.get("1.0", tk.END).strip()
        use_search = self.use_search_var.get()
        search_topic = self.search_topic_var.get().strip()

        if not text and not (use_search and search_topic):
            messagebox.showerror("错误", "请输入文本，或启用联网搜索并输入主题！")
            return

        level = self.level_var.get().strip()
        genre = self.genre_var.get().strip()
        try:
            max_retries = int(self.retries_var.get().strip())
            if max_retries < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "重试次数必须为非负整数！")
            return

        generate_vocab = self.vocab_var.get()

        self.generate_btn.config(state=tk.DISABLED)
        self.running = True
        self.clear_output()
        self.final_output = ""
        self.set_status("生成中...", "blue")
        self.progress['value'] = 0

        thread = threading.Thread(
            target=self.run_agent,
            args=(text, level, genre, max_retries, use_search, search_topic, generate_vocab),
            daemon=True
        )
        thread.start()

    def run_agent(self, text, level, genre, max_retries, use_search, search_topic, generate_vocab):
        try:
            self.progress_queue.put(5)
            self.log_output("正在启动四六级出题 Agent")
            self.log_output(f"级别: {level}  |  体裁: {genre}  |  最大重试: {max_retries} 次")
            if use_search:
                self.log_output(f"联网搜索主题: {search_topic}")
            self.log_output("-" * 50)

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
                "include_vocab": generate_vocab,
            }

            config = {"configurable": {"thread_id": "ui_session"}}

            # 使用 stream 实现节点级进度反馈；仅当 stream API 不兼容时兜底到 invoke
            final_state = dict(initial_state)
            stream_api_failed = False
            try:
                for event in self.agent.stream(initial_state, config=config):
                    # event 格式: {node_name: {state_key: value, ...}}
                    for node_name, state_update in event.items():
                        final_state.update(state_update)
                        progress = NODE_PROGRESS.get(node_name)
                        if progress:
                            self.progress_queue.put(progress)
                            label = NODE_LABELS.get(node_name, node_name)
                            self.log_output(f"   ✓ {label} 完成 ({progress}%)")
            except (AttributeError, TypeError) as api_err:
                # 仅捕获 stream 方法不存在或签名不兼容的情况；真实运行时错误向上抛出
                stream_api_failed = True
                self.log_output(f"流式进度不可用，切换为标准模式: {api_err}")

            # API 不兼容时兜底到 invoke
            if stream_api_failed:
                final_state = self.agent.invoke(initial_state, config=config)

            output = final_state["final_output"]
            self.final_output = output

            self.progress_queue.put(100)
            self.log_output(output)
            self.log_output(f"\n统计: 文章重试 {final_state['article_retries']} 次, 题目重试 {final_state['questions_retries']} 次。")
            self.set_status("✅ 生成完成", "green")

        except Exception as e:
            self.log_output(f"\n发生错误: {str(e)}")
            self.set_status("生成失败", "red")
            import traceback
            self.log_output(traceback.format_exc())
            self.progress_queue.put(-1)
        finally:
            self.root.after(0, self.enable_button)

    def enable_button(self):
        self.generate_btn.config(state=tk.NORMAL)
        self.running = False

    def export_word(self):
        """导出为 Word 文档（仅导出最终生成内容，不含运行日志）"""
        if not HAS_DOCX:
            messagebox.showerror("错误", "请先安装 python-docx: pip install python-docx")
            return

        content = self.final_output.strip()
        if not content:
            print("⚠️ 导出跳过：没有可导出的内容，请先生成题目")
            messagebox.showwarning("提示", "没有可导出的内容，请先生成题目")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word 文档", "*.docx"), ("所有文件", "*.*")]
        )
        if not file_path:
            return

        success = export_to_word(content, file_path)
        if success:
            print(f"✅ Word 已导出到：{file_path}")
            messagebox.showinfo("成功", f"已导出到：{file_path}")
        else:
            print("❌ Word 导出失败：生成文档时发生错误")
            messagebox.showerror("导出失败", "导出Word文档时发生错误")