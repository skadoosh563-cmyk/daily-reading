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


def _payload(cfg: dict, messages: list[dict], force_json: bool, stream: bool) -> dict:
    llm = cfg["llm"]
    p = {
        "model": llm["model"],
        "messages": messages,
        "temperature": llm.get("temperature", 0.3),
        "max_tokens": llm.get("max_tokens", 8192),
        "stream": stream,
    }
    if force_json:
        p["response_format"] = {"type": "json_object"}
    return p


def _headers(cfg: dict) -> dict:
    return {
        "Authorization": f"Bearer {cfg['llm']['api_key']}",
        "Content-Type": "application/json",
    }


def _warn_if_truncated(finish_reason: str | None) -> None:
    if finish_reason == "length":
        print("  [警告] 输出被 max_tokens 截断（finish_reason=length），"
              "这篇很可能解析失败，可调高 config.yaml 里的 llm.max_tokens")


def _post_stream(cfg: dict, messages: list[dict], force_json: bool) -> str:
    """流式请求，边收边拼。

    现在不少中转站（例如 svip 分组）已经**禁用非流式请求**，
    直接返回 400「请使用 stream=true」，所以流式才是主路径。
    """
    llm = cfg["llm"]
    resp = requests.post(
        _endpoint(llm["base_url"]),
        headers=_headers(cfg),
        json=_payload(cfg, messages, force_json, True),
        timeout=llm.get("timeout", 300),
        stream=True,
    )
    if resp.status_code >= 400:
        detail = resp.content.decode("utf-8", "replace")[:400]
        raise RuntimeError(f"HTTP {resp.status_code}: {detail}")

    parts: list[str] = []
    finish = None
    for raw in resp.iter_lines(decode_unicode=False):
        if not raw:
            continue
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            obj = json.loads(data)
        except json.JSONDecodeError:
            continue
        choices = obj.get("choices") or []
        if not choices:
            continue
        ch = choices[0]
        piece = (ch.get("delta") or {}).get("content")
        if piece:
            parts.append(piece)
        if ch.get("finish_reason"):
            finish = ch["finish_reason"]
    _warn_if_truncated(finish)
    return "".join(parts)


def _post_plain(cfg: dict, messages: list[dict], force_json: bool) -> str:
    llm = cfg["llm"]
    resp = requests.post(
        _endpoint(llm["base_url"]),
        headers=_headers(cfg),
        json=_payload(cfg, messages, force_json, False),
        timeout=llm.get("timeout", 300),
    )
    if resp.status_code >= 400:
        detail = resp.content.decode("utf-8", "replace")[:400]
        raise RuntimeError(f"HTTP {resp.status_code}: {detail}")
    # 注意：部分中转站的响应头只写 application/json、不带 charset，
    # 此时 requests 会按 ISO-8859-1 解码，模型返回的中文就会变成
    # "é£é£" 这种乱码（英文不受影响，所以很容易漏看）。
    # JSON 标准规定就是 UTF-8，这里直接拿原始字节强制按 UTF-8 解析。
    data = json.loads(resp.content.decode("utf-8"))
    choice = data["choices"][0]
    _warn_if_truncated(choice.get("finish_reason"))
    return choice["message"]["content"]


def _post(cfg: dict, messages: list[dict], force_json: bool) -> str:
    """先走流式；万一服务商不支持流式，再退回非流式。"""
    try:
        return _post_stream(cfg, messages, force_json)
    except RuntimeError as exc:
        if "stream" in str(exc).lower():
            print("  [提示] 流式请求被拒，改用非流式重试")
            return _post_plain(cfg, messages, force_json)
        raise


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

    # JSON 格式错误多半是模型的偶发输出（同一篇重跑往往就好），所以解析失败要重试。
    # 最多 3 次，全失败才抛给上层 —— 上层会换下一篇候选。
    for attempt in range(1, 4):
        # 先试 JSON 模式；有的服务商不支持，失败就去掉重试
        try:
            raw = _post(cfg, messages, force_json=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  [提示] JSON 模式不可用（{exc}），改用普通模式重试")
            raw = _post(cfg, messages, force_json=False)
        try:
            result = _parse_json(raw)
            break
        except ValueError as exc:
            if attempt >= 3:
                raise
            print(f"  [重试 {attempt}/2] 解析失败（{exc}），再生成一次")
            messages = messages + [{
                "role": "user",
                "content": "上一次输出不是合法 JSON。请重新输出：只用双引号、字段之间必须有逗号、"
                           "不要输出 markdown 代码块或任何解释文字，整段必须能被 JSON 解析。",
            }]

    result.setdefault("translation", [])
    result.setdefault("vocab", [])
    result.setdefault("grammar", [])
    result.setdefault("questions", [])
    return result
