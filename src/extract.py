"""从文章链接里把正文抠出来。

RSS 里通常只有一两句摘要，做精读远远不够，所以要顺着链接把正文抓下来。
用 trafilatura 做正文抽取，它比 newspaper3k 稳，也比 Readability 干净。
抓不到就退回到 RSS 摘要，保证流程不中断。
"""
from __future__ import annotations

import re

import requests
import trafilatura

from .fetch import HEADERS

_MIN_WORDS = 120


def fetch_html(url: str, timeout: int = 30) -> str:
    """先用自己的请求头抓；失败再让 trafilatura 自己抓一次。"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:  # noqa: BLE001
        print(f"  [抓取重试] {type(exc).__name__}，换 trafilatura 再试一次")
    try:
        return trafilatura.fetch_url(url) or ""
    except Exception as exc:  # noqa: BLE001
        print(f"  [正文抓取失败] {type(exc).__name__} {exc}")
        return ""


def clean(text: str) -> str:
    """规整一下段落：去掉多余空行和行内空白。"""
    if not text:
        return ""
    lines = []
    for para in text.split("\n"):
        para = re.sub(r"[ \t\u00a0]+", " ", para).strip()
        if para:
            lines.append(para)
    return "\n\n".join(lines)


def extract(url: str, fallback: str = "", title: str = "") -> str:
    """返回正文。抓不到就用 fallback（RSS 摘要）。"""
    html_text = fetch_html(url)
    body = ""
    if html_text:
        body = trafilatura.extract(
            html_text,
            url=url,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        body = clean(body or "")
        if body and len(body.split()) < _MIN_WORDS:
            body = ""

    if not body:
        body = clean(fallback)
        if body:
            print("  [提示] 正文抽取不完整，退回使用 RSS 摘要")
    body = _drop_repeated_title(body, title)
    return _strip_trailing_boilerplate(body)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _drop_repeated_title(body: str, title: str) -> str:
    """抽取结果常常把标题当成第一段带进来，跟正文标题重复，去掉。"""
    if not body or not title:
        return body
    parts = body.split("\n\n")
    if not parts:
        return body
    first, target = _norm(parts[0]), _norm(title)
    if first and target and (first == target or first.startswith(target) or target.startswith(first)):
        return "\n\n".join(parts[1:]).strip()
    return body


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n\n") if p.strip()]


# 页面尾部的站点导航/推荐位。trafilatura 偶尔会把这些一起抽进来，
# 表现为一串很短的独立段落（"Deep Dive"、"Stay connected"、推荐标题）。
# 遇到这类标记就从那里截断。
_BOILERPLATE_RE = re.compile(
    r"^(deep dive|stay connected|sign up|subscribe|related\b|read more\b|more from\b|"
    r"share this\b|most popular|recommended|newsletter|follow us|topics\b|tags\b|"
    r"about the author|image credits?\b)",
    re.I,
)
# 这些短语出现在正文里基本一定是页脚（可以是长段）
_FOOTER_RE = re.compile(
    r"(this article first appeared in|sign up for our|subscribe to our|"
    r"this story was originally published|read the original article|"
    r"for more coverage of|never miss a story)",
    re.I,
)


def _strip_trailing_boilerplate(body: str) -> str:
    parts = body.split("\n\n")
    for i, p in enumerate(parts):
        if i < 3:
            continue  # 至少保留三段，避免误伤正文
        if _FOOTER_RE.search(p):
            return "\n\n".join(parts[:i]).strip()
        if len(p) <= 90 and _BOILERPLATE_RE.match(p.strip()):
            return "\n\n".join(parts[:i]).strip()
    return body
