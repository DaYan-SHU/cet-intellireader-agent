// server.js — 四六级出题 Agent 网页版服务端
// Node.js 20+，零外部依赖。业务逻辑与 core/nodes.py 保持一致（提示词逐字迁移）。
const http = require("http");
const fs = require("fs");
const path = require("path");

const HOST = "0.0.0.0";
const PORT = Number(process.env.PORT) || 8000;
const DEEPSEEK_API_KEY = process.env.DEEPSEEK_API_KEY || "";
const TAVILY_API_KEY = process.env.TAVILY_API_KEY || "";
const DEEPSEEK_URL = "https://api.deepseek.com/chat/completions";
const TAVILY_URL = "https://api.tavily.com/search";
const INDEX_HTML = path.join(__dirname, "public", "index.html");
const PUBLIC_DIR = path.join(__dirname, "public");
const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".webp": "image/webp",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
};

// 与 ui/streamlit_app.py 保持一致的进度映射
const NODE_PROGRESS = {
  search: 8,
  analyze: 18,
  gen_article: 32,
  check_article: 42,
  gen_questions: 56,
  check_questions: 66,
  gen_answers: 76,
  gen_vocabulary: 86,
  finalize: 96,
};
const NODE_LABELS = {
  search: "联网搜索",
  analyze: "素材分析",
  gen_article: "生成文章",
  check_article: "文章质检",
  gen_questions: "生成题目",
  check_questions: "题目质检",
  gen_answers: "生成答案解析",
  gen_vocabulary: "生成词汇表",
  finalize: "整合输出",
};

// ============== LLM 调用（DeepSeek） ==============
async function llm(prompt) {
  let lastErr;
  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      const resp = await fetch(DEEPSEEK_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${DEEPSEEK_API_KEY}`,
        },
        body: JSON.stringify({
          model: "deepseek-chat",
          temperature: 0.7,
          messages: [{ role: "user", content: prompt }],
        }),
      });
      if (!resp.ok) {
        const body = await resp.text().catch(() => "");
        throw new Error(`DeepSeek API ${resp.status}: ${body.slice(0, 300)}`);
      }
      const data = await resp.json();
      const content = data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content;
      if (typeof content !== "string") throw new Error("DeepSeek 返回格式异常");
      return content;
    } catch (err) {
      lastErr = err;
      if (attempt < 2) await new Promise((r) => setTimeout(r, 1500));
    }
  }
  throw lastErr;
}

// ============== 联网搜索（Tavily，可选） ==============
async function searchAndSummarize(topic) {
  if (!TAVILY_API_KEY) return "";
  try {
    const resp = await fetch(TAVILY_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: TAVILY_API_KEY, query: topic, max_results: 3 }),
    });
    if (!resp.ok) throw new Error(`Tavily ${resp.status}`);
    const results = await resp.json();
    const prompt = `
        请根据以下搜索结果，整理出一篇适合作为四六级阅读理解材料的中文文本。

        【搜索主题】${topic}
        【搜索结果】${JSON.stringify(results)}

        【要求】
        1. 整合关键信息，生成 400-600 字的中文文本
        2. 结构清晰，适合作为考试阅读材料
        3. 文本内容基于四六级大纲展开，段落分明，逻辑连贯
        `;
    return await llm(prompt);
  } catch (err) {
    console.error("搜索失败:", err.message);
    return "";
  }
}

// ============== 工具函数（与 utils/helpers.py、core/nodes.py 一致） ==============
function detectLanguage(text) {
  const chineseChars = (text.match(/[\u4e00-\u9fff]/g) || []).length;
  const totalChars = text.trim().length;
  if (totalChars === 0) return "unknown";
  return chineseChars / totalChars > 0.3 ? "zh" : "en";
}

function extractChineseSummary(analysis) {
  const separators = ["第二部分：英文大纲", "第二部分:英文大纲", "第二部分： 英文大纲", "【英文大纲】", "英文大纲"];
  for (const sep of separators) {
    if (analysis.includes(sep)) {
      let stripped = analysis.split(sep)[0].trim().replace(/^[-—]+|[-—]+$/g, "").trim();
      const prefixes = [
        "第一部分：中文理解摘要", "第一部分:中文理解摘要",
        "第一部分：中文摘要", "第一部分:中文摘要",
        "【中文理解摘要】", "【中文摘要】",
        "中文理解摘要", "中文摘要",
      ];
      for (const prefix of prefixes) {
        if (stripped.startsWith(prefix)) {
          stripped = stripped.slice(prefix.length).trim().replace(/^[-—]+|[-—]+$/g, "").trim();
          break;
        }
      }
      if (stripped) return stripped;
    }
  }
  const cleaned = analysis.trim().replace(/^[-—]+|[-—]+$/g, "").trim();
  return cleaned.slice(0, 150) + (cleaned.length > 150 ? "..." : "");
}

function extractEnglishOutline(analysis) {
  const separators = ["第二部分：英文大纲", "第二部分:英文大纲", "第二部分： 英文大纲", "【英文大纲】", "英文大纲"];
  for (const sep of separators) {
    if (analysis.includes(sep)) {
      const parts = analysis.split(sep);
      if (parts.length > 1) {
        const outline = parts[1].trim().replace(/^[-—]+|[-—]+$/g, "").trim();
        if (outline) return outline;
      }
    }
  }
  return "";
}

// ============== 工作流节点（提示词与 core/nodes.py 逐字一致） ==============
function genreInstruction(genre) {
  return {
    议论文: "重点提取中心论点、分论点和论据。",
    说明文: "重点提取核心概念、特征、分类或过程。",
    叙事文: "重点提取人物、情节主线、时间地点和冲突。",
    自动: "根据文本实际内容自动判断体裁并提取相应要素。",
  }[genre] || "根据文本实际内容自动判断体裁并提取相应要素。";
}

async function analyzeText(state) {
  const lang = detectLanguage(state.input_text);
  const gi = genreInstruction(state.genre);
  const outlineSpec = `Title: （完整的英文标题）
Introduction: （用1-2个完整英文句子介绍文章背景和主题）
Body Paragraph 1: （用1个完整英文句子概括第一个主体段落的主旨）
Body Paragraph 2: （用1个完整英文句子概括第二个主体段落的主旨）
Body Paragraph 3 (if applicable): （如果原文有三个主体段落，用1个完整英文句子概括第三个主体段落；否则省略此项）
Conclusion: （用1个完整英文句子概括结论）`;
  const prompt = `
你是一位资深英语教育专家和四六级命题专家。请${lang === "en" ? "阅读以下英文文本，提炼主题并生成英文文章大纲" : "仔细阅读以下中文文本，理解后生成英文大纲"}。

【输入文本】${state.input_text}
【体裁提示】${gi}

请严格按照以下两个部分输出，不要添加任何额外标题、解释或分隔线：

第一部分：中文理解摘要
（用50-80字中文概括文章核心内容）

第二部分：英文大纲
${outlineSpec}

注意：每个部分都必须提供实质内容，不要只写短语或省略。
`;
  const analysis = await llm(prompt);
  return {
    analysis,
    analysis_summary: extractChineseSummary(analysis),
    analysis_outline: extractEnglishOutline(analysis),
    article_retries: 0,
    questions_retries: 0,
  };
}

async function generateArticle(state) {
  const critique = state.critique || "";
  const refine = critique ? `请根据以下意见修改：${critique}` : "请直接生成高质量文章。";
  let outline = state.analysis_outline || "";
  if (!outline) outline = extractEnglishOutline(state.analysis || "");
  const wordCount = state.level.includes("四级") ? "400-450" : "450-550";
  const prompt = `
    你是四六级命题专家。根据以下分析报告生成英文文章。

    【分析报告】${state.analysis}
    【英文大纲】${outline}
    【修改指令】${refine}

    【要求】
    1. 级别:${state.level}，词数:${wordCount}
    2. 严格基于大纲展开，段落分明，逻辑连贯
    3. 使用标准四六级考试风格，词汇地道

    只输出纯英文文章，不要包含中文解释。
    `;
  const article = await llm(prompt);
  return { article, article_retries: state.article_retries + 1, critique: "" };
}

async function checkArticleQuality(state) {
  const wordCount = state.level.includes("四级") ? "400-450" : "450-550";
  const prompt = `
    请审核以下文章是否符合${state.level}标准。

    【文章】${state.article}

    【审核标准】
    1. 词数是否达标（${wordCount}）？
    2. 主题清晰，与原文一致？
    3. 无语法错误或中式英语？
    4. 适合作为阅读理解材料？

    通过输出"PASS"，否则输出"FAIL: 具体建议"
    `;
  const result = (await llm(prompt)).trim();
  if (result.startsWith("PASS")) return { critique: "PASS" };
  return { critique: result.replace("FAIL:", "").trim() };
}

async function generateQuestions(state) {
  const critique = state.critique || "";
  const refine = critique ? `请根据以下意见修改：${critique}` : "直接生成标准题目。";
  const prompt = `
    请根据以下文章生成${state.level}仔细阅读题。

    【文章】${state.article}
    【修改指令】${refine}

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
    `;
  let questions = await llm(prompt);
  const match = questions.match(/\n\s*46\./);
  if (match) questions = questions.slice(match.index).trim();
  return { questions, questions_retries: state.questions_retries + 1, critique: "" };
}

async function checkQuestionsQuality(state) {
  const prompt = `
    审核以下题目是否专业。

    【题目】${state.questions}

    【标准】
    1. 恰好5道题？
    2. 包含主旨、细节、推理、词汇题？
    3. 每道题都有答题留白？
    4. 选项设置合理？

    通过输出"PASS"，否则输出"FAIL: 建议"
    `;
  const result = (await llm(prompt)).trim();
  if (result.startsWith("PASS")) return { critique: "PASS" };
  return { critique: result.replace("FAIL:", "").trim() };
}

async function generateAnswers(state) {
  const prompt = `
    根据以下文章和题目生成答案与解析。

    【文章】${state.article}
    【题目】${state.questions}

    【要求】
    1. 每道题给出正确答案（如：46. A）
    2. 中文解析，说明正确和错误原因

    【格式】
    46. 答案：A
    解析：...
    47. 答案：B
    解析：...
    `;
  return { answers: await llm(prompt) };
}

async function generateVocabulary(state) {
  const prompt = `
    从以下文章中提取10-15个重点词汇，生成词汇表。

    【文章】${state.article}

    【要求】
    1. 选取对理解文章至关重要的四六级词汇
    2. 输出格式：每行一个词汇，英文、词性、中文释义之间用制表符（Tab键）分隔
    3. 不要添加任何表头、序号、竖线或其他装饰符号
    4. 按字母顺序排列
    5. 示例格式：
    abandon\tv.\t放弃；抛弃
    ability\tn.\t能力；才能
    `;
  return { vocabulary: await llm(prompt) };
}

function finalize(state) {
  const sections = [
    "========================================",
    `       ${state.level} 阅读理解模拟题`,
    "========================================",
    "",
    "【文章正文】",
    state.article,
    "",
    "【题目部分】",
    state.questions,
    "",
    "【答案与解析】",
    state.answers || "",
  ];
  if (state.include_vocab) {
    sections.push("", "【词汇表】", state.vocabulary || "");
  }
  const summary = state.analysis_summary || extractChineseSummary(state.analysis || "");
  sections.push("", "【素材理解摘要】", summary);
  const outline = state.analysis_outline || extractEnglishOutline(state.analysis || "");
  if (outline) sections.push("", "【英文大纲】", outline);
  return { final_output: sections.join("\n") };
}

// ============== 工作流编排（与 core/graph.py 一致） ==============
async function runWorkflow(state, emit, isCancelled) {
  const step = async (name, fn) => {
    if (isCancelled()) throw new Error("客户端已断开，任务已取消");
    if (name === "gen_article" || name === "gen_questions") {
      emit({ type: "progress", node: name, pct: NODE_PROGRESS[name], label: `${NODE_LABELS[name]}（第 ${name === "gen_article" ? state.article_retries + 1 : state.questions_retries + 1} 次尝试）`, phase: "start" });
    }
    const update = await fn(state);
    Object.assign(state, update);
    const pct = NODE_PROGRESS[name];
    if (pct) emit({ type: "progress", node: name, pct, label: NODE_LABELS[name], phase: "done", message: `✓ ${NODE_LABELS[name]} 完成 (${pct}%)` });
  };

  // search 节点
  if (state.use_search && state.search_topic) {
    await step("search", async () => {
      const text = await searchAndSummarize(state.search_topic);
      return text ? { input_text: text } : { input_text: state.input_text };
    });
  } else {
    await step("search", async () => ({ input_text: state.input_text }));
  }

  await step("analyze", analyzeText);

  // 文章生成 + 质检循环
  await step("gen_article", generateArticle);
  await step("check_article", checkArticleQuality);
  while (state.critique !== "PASS" && state.article_retries < state.max_retries) {
    await step("gen_article", generateArticle);
    await step("check_article", checkArticleQuality);
  }

  // 题目生成 + 质检循环
  await step("gen_questions", generateQuestions);
  await step("check_questions", checkQuestionsQuality);
  while (state.critique !== "PASS" && state.questions_retries < state.max_retries) {
    await step("gen_questions", generateQuestions);
    await step("check_questions", checkQuestionsQuality);
  }

  await step("gen_answers", generateAnswers);
  await step("gen_vocabulary", generateVocabulary);
  await step("finalize", finalize);
  return state;
}

// ============== SSE 生成接口 ==============
function handleGenerate(req, res, body) {
  res.writeHead(200, {
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
    "X-Accel-Buffering": "no",
  });

  const emit = (payload) => {
    if (!res.destroyed) {
      try { res.write(`data: ${JSON.stringify(payload)}\n\n`); } catch (_) { /* 连接已断开 */ }
    }
  };
  const ping = setInterval(() => {
    if (!res.destroyed) { try { res.write(": ping\n\n"); } catch (_) { /* ignore */ } }
  }, 15000);

  const ac = new AbortController();
  req.on("close", () => ac.abort(new Error("client closed")));
  const isCancelled = () => res.destroyed;

  (async () => {
    try {
      if (!DEEPSEEK_API_KEY) throw new Error("服务端未配置 DEEPSEEK_API_KEY 环境变量");
      const input = JSON.parse(body);
      const text = String(input.text || "").trim();
      const searchTopic = String(input.searchTopic || "").trim();
      const useSearch = Boolean(input.useSearch);
      if (!text && !(useSearch && searchTopic)) {
        throw new Error("请输入素材文本，或勾选「启用联网搜索」并填写搜索主题");
      }
      const level = input.level === "四级" ? "四级" : "六级";
      const genre = ["自动", "议论文", "说明文", "叙事文"].includes(input.genre) ? input.genre : "自动";
      const maxRetries = Math.min(Math.max(Number(input.maxRetries) || 0, 0), 5);

      const logs = [
        "正在启动四六级出题 Agent",
        `级别: ${level}  |  体裁: ${genre}  |  最大重试: ${maxRetries} 次`,
      ];
      if (useSearch) logs.push(`联网搜索主题: ${searchTopic}`);
      logs.push("----------------------------------------");
      for (const m of logs) emit({ type: "log", message: m });

      const state = {
        input_text: text,
        level,
        genre,
        analysis: "",
        analysis_summary: "",
        analysis_outline: "",
        article: "",
        questions: "",
        answers: "",
        vocabulary: "",
        critique: "",
        article_retries: 0,
        questions_retries: 0,
        max_retries: maxRetries,
        use_search: useSearch,
        search_topic: searchTopic,
        include_vocab: input.includeVocab !== false,
        final_output: "",
      };

      const final = await runWorkflow(state, emit, isCancelled);
      emit({
        type: "done",
        output: final.final_output,
        articleRetries: final.article_retries,
        questionsRetries: final.questions_retries,
        level,
        runLabel: `${level} · 体裁 ${genre} · 最大重试 ${maxRetries} 次`,
      });
    } catch (err) {
      const message = err && err.message === "client closed" ? "" : (err && err.message) || String(err);
      if (message && !res.destroyed) emit({ type: "error", message });
      if (message) console.error("生成失败:", message);
    } finally {
      clearInterval(ping);
      if (!res.destroyed) res.end();
    }
  })();
}

// ============== HTTP 服务 ==============
const server = http.createServer((req, res) => {
  const url = req.url.split("?")[0];

  if (req.method === "GET" && (url === "/" || url === "/index.html")) {
    fs.readFile(INDEX_HTML, (err, data) => {
      if (err) {
        res.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
        res.end("index.html 加载失败");
        return;
      }
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end(data);
    });
    return;
  }

  if (req.method === "GET" && url === "/favicon.ico") {
    res.writeHead(204);
    res.end();
    return;
  }

  // 静态资源（仅允许 public/ 下的单层文件名，防目录穿越）
  if (req.method === "GET" && /^\/[A-Za-z0-9._-]+$/.test(url)) {
    const filePath = path.join(PUBLIC_DIR, url.slice(1));
    fs.readFile(filePath, (err, data) => {
      if (err) {
        res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
        res.end("Not Found");
        return;
      }
      const ext = path.extname(filePath).toLowerCase();
      res.writeHead(200, {
        "Content-Type": MIME_TYPES[ext] || "application/octet-stream",
        "Cache-Control": "public, max-age=3600",
      });
      res.end(data);
    });
    return;
  }

  if (req.method === "POST" && url === "/api/generate") {
    const chunks = [];
    let size = 0;
    let overflow = false;
    req.on("data", (chunk) => {
      size += chunk.length;
      if (size > 1_000_000) { overflow = true; req.destroy(); return; }
      chunks.push(chunk);
    });
    req.on("error", () => { /* 客户端中断 */ });
    req.on("end", () => {
      if (overflow) return;
      const body = Buffer.concat(chunks).toString("utf8");
      if (!body) {
        res.writeHead(400, { "Content-Type": "text/plain; charset=utf-8" });
        res.end("请求体为空");
        return;
      }
      handleGenerate(req, res, body);
    });
    return;
  }

  res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
  res.end("Not Found");
});

// 长时 SSE 响应：禁用请求超时
server.requestTimeout = 0;
server.headersTimeout = 60000;

server.listen(PORT, HOST, () => {
  console.log(`四六级出题 Agent 已启动: http://${HOST}:${PORT}`);
  if (!DEEPSEEK_API_KEY) console.warn("警告: 未配置 DEEPSEEK_API_KEY 环境变量，生成功能不可用");
});
