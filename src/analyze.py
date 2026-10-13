"""调用大模型，把一篇英文文章加工成一份精读材料。"""
from __future__ import annotations

import json
import re

import requests

SYSTEM_PROMPT = """你是一位给中国读者做外刊精读的资深英语老师，擅长把英文报道拆解成可直接使用的学习材料。
你的输出会被程序直接解析成 JSON，所以必须严格遵守格式要求，不要输出任何 JSON 之外的内容。"""

USER_TEMPLATE = """请对下面这篇英文文章做精读拆解。

【文章信息】
来源：{source}
标题：{title}
链接：{url}

【文章正文】
{body}

【任务要求】
1. 面向 {level} 水平的中国读者，解释用中文，例句保留英文并附中文翻译。
2. 挑选 {vocab_count} 个真正值得学的词或固定搭配：不要挑 the、make 这种基础词，也不要挑过于生僻的专业术语。优先选「读外刊常遇到、但自己不确定用法」的词。
3. 拆解 {grammar_count} 个长难句或句式亮点：要指出具体是什么结构（如倒装、插入语、省略、虚拟语气、后置定语），并解释为什么这么写。
4. 逐段给出中文翻译，段落顺序务必和原文完全一致，段数也要一致。
5. 出 {question_count} 道理解题：考查是否真的读懂了文章（主旨、作者态度、细节推断），不要考单纯的单词释义；每题给参考答案。
6. 全文难度按 CEFR 给出评级（A2/B1/B2/C1/C2）。

【输出格式】只输出一个 JSON 对象，不要加 markdown 代码块，不要加任何解释文字：
{{
  "title_zh": "标题的中文翻译",
  "level": "难度评级，如 B2",
  "word_count": 文章英文词数(整数),
  "summary_zh": "3-5 句话的中文导读，讲清楚这篇在说什么、为什么值得读",
  "vocab": [
    {{"word": "词或短语", "pos": "词性缩写如 n./v./adj.", "phonetic": "音标", "meaning_zh": "在本句中的中文含义", "example_en": "来自文章的英文原句", "example_zh": "该句中文翻译"}}
  ],
  "grammar": [
    {{"sentence": "英文原句", "point": "结构名称", "explain_zh": "用中文讲清这个结构怎么用、为什么这里这么写"}}
  ],
  "translation": [
    {{"en": "第一段英文原文", "zh": "第一段中文翻译"}}
  ],
  "questions": [
    {{"q": "英文题目", "a": "参考答案，中文作答"}}
  ]
}}"""


def _endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def _post(cfg: dict, messages: list[dict], force_json: bool) -> dict:
    llm = cfg["llm"]
    payload = {
        "model": llm["model"],
        "messages": messages,
        "temperature": llm.get("temperature", 0.3),
        "max_tokens": llm.get("max_tokens", 8192),
    }
    if force_json:
        payload["response_format"] = {"type": "json_object"}

    resp = requests.post(
        _endpoint(llm["base_url"]),
        headers={
            "Authorization": f"Bearer {llm['api_key']}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=llm.get("timeout", 300),
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _parse_json(text: str) -> dict:
    """模型偶尔会裹一层代码块或加几句废话，这里兜一下。"""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("模型返回的内容里找不到合法 JSON")


def analyze(cfg: dict, source: str, title: str, url: str, body: str) -> dict:
    study = cfg["study"]
    user = USER_TEMPLATE.format(
        source=source,
        title=title,
        url=url,
        body=body,
        level=study.get("level", "B2"),
        vocab_count=study.get("vocab_count", 10),
        grammar_count=study.get("grammar_count", 3),
        question_count=study.get("question_count", 3),
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]

    # 先试 JSON 模式；有的服务商不支持，失败就去掉重试
    try:
        raw = _post(cfg, messages, force_json=True)
    except Exception as exc:  # noqa: BLE001
        print(f"  [提示] JSON 模式不可用（{exc}），改用普通模式重试")
        raw = _post(cfg, messages, force_json=False)

    result = _parse_json(raw)
    result.setdefault("translation", [])
    result.setdefault("vocab", [])
    result.setdefault("grammar", [])
    result.setdefault("questions", [])
    return result
