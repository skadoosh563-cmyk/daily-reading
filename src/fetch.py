"""RSS 抓取与候选文章筛选。"""
from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import feedparser
import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# 不适合精读的内容形态：滚动直播、图集、视频、播客、测验、简报、讣告
# 加这一层过滤的原因：RSS 里混着大量 live blog，抓下来是 80 多段带时间戳的
# 碎片更新，根本没法当精读材料。按标题和链接形态提前剔掉。
_BAD_TITLE_RE = re.compile(
    r"(live blog|live updates?\b|live coverage|live news|\blive\s*[:\-–—]|"
    r"as it happened|minute[- ]by[- ]minute|"
    r"\bwatch\b\s*:|\blisten\b\s*:|in pictures|in charts|in maps|photo gallery|"
    r"\bpodcast\b|\bquiz\b|crossword|horoscope|obituar|"
    r"\brecap\b|\broundup\b|morning briefing|newsletter|"
    r"what we know so far|things to know|"
    r"\bweather forecast\b|\bdeath notices\b|\bletters\b\s*:|\bcorrections\b)",
    re.I,
)
_BAD_URL_RE = re.compile(
    r"(/live/|/liveblog|/live-news|/gallery/|/pictures?/|/video/|/videos/|"
    r"/podcasts?/|/audio/|/interactive/|/interactives/|/quiz/|/crossword|"
    r"\.mp3$|/tag/|/topics?/)",
    re.I,
)


def is_readable(title: str, link: str) -> bool:
    """判断这篇是否值得作为精读候选。"""
    if _BAD_TITLE_RE.search(title or ""):
        return False
    if _BAD_URL_RE.search(link or ""):
        return False
    return True


# 广播/播客转写稿的特征。这类文本有大量 SOUNDBITE、(LAUGHTER) 之类的现场提示，
# 句子破碎、语气词多，是"听写稿"不是"文章"，做精读很别扭。抓完正文才发现，
# 所以放在正文之后判。
_TRANSCRIPT_RE = re.compile(
    r"(SOUNDBITE|\bBYLINE\b|\bHOST\s*:|\(LAUGHTER\)|\(MUSIC\)|\bSPEAKER \d|\(\d{2}:\d{2}\))"
)


def looks_like_transcript(text: str) -> bool:
    hits = len(_TRANSCRIPT_RE.findall((text or "")[:2500]))
    return hits >= 3


def usable(text: str, cfg: dict) -> tuple[bool, str]:
    """正文是否可用。返回 (是否可用, 不可用的原因)。"""
    if looks_like_transcript(text):
        return False, "广播/播客转写稿"
    if not within_length(text, cfg):
        sel = cfg["selection"]
        return False, (
            f"{word_count(text)} 词，不在 "
            f"{sel.get('min_words')}—{sel.get('max_words')} 区间"
        )
    return True, ""


def strip_html(text: str) -> str:
    """把 RSS 摘要里的 HTML 标签去掉，顺便解一下实体。"""
    if not text:
        return ""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = _TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", html.unescape(text)).strip()


@dataclass
class Candidate:
    title: str
    link: str
    source: str
    summary: str
    published: datetime | None = None

    @property
    def key(self) -> str:
        """去重用的稳定 ID。"""
        return hashlib.md5((self.link or self.title).strip().encode("utf-8")).hexdigest()[:16]

    @property
    def published_str(self) -> str:
        return self.published.strftime("%Y-%m-%d") if self.published else ""


def _parse_time(entry) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        t = entry.get(field)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    return None


def fetch_feed(source: dict, timeout: int = 30) -> list[Candidate]:
    """抓一个 RSS 源。失败时返回空列表，不影响其它源。"""
    url, name = source["url"], source.get("name", source["url"])
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(f"  [跳过] {name}：{type(exc).__name__} {exc}")
        return []

    parsed = feedparser.parse(resp.content)
    out: list[Candidate] = []
    for entry in parsed.entries:
        link = (entry.get("link") or "").strip()
        title = strip_html(entry.get("title") or "")
        if not link or not title:
            continue
        if not is_readable(title, link):
            continue
        summary = strip_html(
            entry.get("summary") or entry.get("description") or ""
        )
        out.append(
            Candidate(
                title=title,
                link=link,
                source=name,
                summary=summary,
                published=_parse_time(entry),
            )
        )
    print(f"  [成功] {name}：{len(out)} 条")
    return out


def collect(cfg: dict, seen: set[str]) -> list[Candidate]:
    """抓全部启用的源，去掉看过的和太旧的。"""
    sel = cfg["selection"]
    prefer_days = int(sel.get("prefer_recent_days", 3) or 0)
    deadline = datetime.now(timezone.utc) - timedelta(days=prefer_days) if prefer_days else None

    pool: list[Candidate] = []
    for source in cfg["sources"]:
        if not source.get("url") or not source.get("enabled", True):
            continue
        for item in fetch_feed(source):
            if item.key in seen:
                continue
            if deadline and item.published and item.published < deadline:
                continue
            pool.append(item)
    return pool


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z][A-Za-z'-]*", text or ""))


def pick(pool: list[Candidate], cfg: dict, want: int | None = None,
         per_source: int | None = None) -> list[Candidate]:
    """按规则挑出候选文章。

    want 可以大于 config 里的 count：正文长度要抓下来才知道，
    所以先多挑几篇当缓冲，抓完再筛。
    per_source 是缓冲模式下放宽的「同源上限」，正式取文时仍用 config 的值。
    """
    sel = cfg["selection"]
    if want is None:
        want = int(sel.get("count", 1))
    max_per_source = int(per_source if per_source is not None
                         else sel.get("max_per_source", 1))

    # 每个来源内部先排好：摘要长的更可能是正经报道，其次看发布时间
    floor = datetime.min.replace(tzinfo=timezone.utc)
    by_source: dict[str, list[Candidate]] = {}
    for item in pool:
        by_source.setdefault(item.source, []).append(item)
    for items in by_source.values():
        items.sort(key=lambda c: (len(c.summary), c.published or floor), reverse=True)

    # 轮询取文：每轮每个来源各取一篇。
    # 这样比"全局按摘要长度排"更稳——避免所有候选都来自同一两个源，
    # 而那两个源恰好正文抓不到（403），一天就白跑了。
    picked: list[Candidate] = []
    taken: dict[str, int] = {s: 0 for s in by_source}
    while len(picked) < want:
        progressed = False
        for src, items in by_source.items():
            if taken[src] >= max_per_source or not items:
                continue
            picked.append(items.pop(0))
            taken[src] += 1
            progressed = True
            if len(picked) >= want:
                break
        if not progressed:
            break
    return picked


def within_length(text: str, cfg: dict) -> bool:
    """正文长度是否落在设定区间内。"""
    sel = cfg["selection"]
    n = _word_count(text)
    return int(sel.get("min_words", 0)) <= n <= int(sel.get("max_words", 10**9))


def word_count(text: str) -> int:
    return _word_count(text)
