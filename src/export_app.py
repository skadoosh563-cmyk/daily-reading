"""导出小程序 / 网页前端用的静态 JSON。

小程序不能直接读 GitHub 仓库文件，但可以请求 HTTPS 接口。
所以这里把每天的归档整理成一份纯静态 JSON，放到 docs/ 下，
再用 GitHub Pages 托管，小程序就能直接 fetch。

好处是不用任何后端、不用云函数、不用数据库——
GitHub Actions 每天生成，Pages 自动发布，小程序只负责展示。
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

PALETTE_VERSION = 1


def _parse_md(md_text: str) -> dict:
    """从 Markdown 里抠出结构化内容。

    比另存一份 JSON 更省事：归档格式已经定了，直接解析它，
    不用维护两套数据。
    """
    out: dict = {
        "title_zh": "", "summary": "", "vocab": [], "grammar": [],
        "questions": [], "translation": [], "article": [],
    }
    if not md_text:
        return out

    lines = md_text.split("\n")
    section = ""
    buffer: list[str] = []
    para_idx = 0

    def flush_translation() -> None:
        nonlocal para_idx
        # 逐段翻译区里，形如「**1.** 英文」+ 空行 + 「中文」
        txt = "\n".join(buffer)
        blocks = re.split(r"\n(?=\*\*\d+\.\*\*)", txt)
        for b in blocks:
            b = b.strip()
            if not b:
                continue
            m = re.match(r"\*\*(\d+)\.\*\*\s*(.*?)\n+(.*)", b, re.S)
            if m:
                out["translation"].append({
                    "idx": int(m.group(1)),
                    "en": m.group(2).strip(),
                    "zh": m.group(3).strip(),
                })
                para_idx += 1

    for raw in lines:
        line = raw.rstrip()
        m = re.match(r"^##\s*[一二三四五六七八九十]+、(.+)$", line)
        if m:
            if section == "逐段翻译":
                flush_translation()
            elif section == "生词表":
                out["vocab"] = _parse_vocab(buffer)
            elif section == "长难句拆解":
                out["grammar"] = _parse_grammar(buffer)
            elif section == "理解题":
                out["questions"] = _parse_questions(buffer)
            elif section == "原文":
                out["article"] = [p.strip() for p in "\n".join(buffer).split("\n\n") if p.strip()]
            section = m.group(1).strip()
            buffer = []
            continue
        buffer.append(line)

    if section == "逐段翻译":
        flush_translation()
    elif section == "生词表":
        out["vocab"] = _parse_vocab(buffer)
    elif section == "长难句拆解":
        out["grammar"] = _parse_grammar(buffer)
    elif section == "理解题":
        out["questions"] = _parse_questions(buffer)
    elif section == "原文":
        out["article"] = [p.strip() for p in "\n".join(buffer).split("\n\n") if p.strip()]

    # 标题和导读
    head = md_text.split("## ", 1)[0]
    for line in head.split("\n"):
        if line.startswith("> 来源："):
            out["meta_line"] = line.lstrip("> ").strip()

    m = re.search(r"^##\s*[一二三四五六七八九十]+、导读\s*\n+(.+?)(?=\n##\s|\Z)",
                  md_text, re.S | re.M)
    if m:
        out["summary"] = m.group(1).strip()

    # 生词表里带例句的部分在表格后面，补进去
    examples = _parse_vocab_examples(md_text)
    for v in out["vocab"]:
        ex = examples.get(v["word"])
        if ex:
            v["example_en"] = ex[0]
            v["example_zh"] = ex[1]
    return out


def _parse_vocab(buffer: list[str]) -> list[dict]:
    items = []
    for line in buffer:
        line = line.strip()
        if not line.startswith("|") or line.startswith("| ---") or "词 |" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 4:
            items.append({
                "word": cells[0], "pos": cells[1],
                "phonetic": cells[2], "meaning_zh": cells[3],
            })
    return items


def _parse_vocab_examples(md_text: str) -> dict[str, tuple[str, str]]:
    """从生词表后半段的列表里取例句。"""
    out: dict[str, tuple[str, str]] = {}
    m = re.search(r"##\s*[一二三四五六七八九十]+、生词表(.*?)(?=\n##|\Z)", md_text, re.S)
    if not m:
        return out
    block = m.group(1)
    for chunk in re.split(r"\n(?=- \*\*)", block):
        chunk = chunk.strip()
        if not chunk.startswith("- **"):
            continue
        word = re.match(r"- \*\*(.+?)\*\*", chunk)
        ex_en = re.search(r"\n\s+- (.+)", chunk)
        ex_zh = re.findall(r"\n\s+- (.+)", chunk)
        if word and len(ex_zh) >= 2:
            out[word.group(1).strip()] = (ex_zh[-2].strip(), ex_zh[-1].strip())
        elif word and ex_en:
            out[word.group(1).strip()] = (ex_en.group(1).strip(), "")
    return out


def _parse_grammar(buffer: list[str]) -> list[dict]:
    items = []
    txt = "\n".join(buffer)
    for chunk in re.split(r"\n(?=\*\*\d+）)", txt):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = re.match(r"\*\*\d+）(.*?)\*\*\s*\n+(.*)", chunk, re.S)
        if not m:
            continue
        sentence = m.group(1).strip()
        rest = m.group(2)
        point = re.search(r"-\s*结构：(.+)", rest)
        explain = re.search(r"-\s*讲解：(.+)", rest, re.S)
        items.append({
            "sentence": sentence,
            "point": point.group(1).strip() if point else "",
            "explain_zh": explain.group(1).strip() if explain else "",
        })
    return items


def _parse_questions(buffer: list[str]) -> list[dict]:
    items = []
    txt = "\n".join(buffer)
    for chunk in re.split(r"\n(?=\*\*\d+\.\*\*)", txt):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = re.match(r"\*\*\d+\.\*\*\s*(.*?)\n+>\s*参考答案：(.+)", chunk, re.S)
        if m:
            items.append({"q": m.group(1).strip(), "a": m.group(2).strip()})
    return items


def build_item(md_path: Path, slug: str, date: str) -> dict | None:
    try:
        md_text = md_path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return None
    parsed = _parse_md(md_text)
    if not parsed.get("vocab") and not parsed.get("translation"):
        return None

    item = {
        "id": slug,
        "date": date,
        "slug": slug,
        "title_zh": _title_from_md(md_path),
        "meta_line": parsed.get("meta_line", ""),
        "summary": parsed.get("summary", ""),
        "vocab": parsed.get("vocab", []),
        "grammar": parsed.get("grammar", []),
        "questions": parsed.get("questions", []),
        "translation": parsed.get("translation", []),
        "article": parsed.get("article", []),
    }

    # 来源、难度、词数、原文链接都从 meta 行里取
    ml = item["meta_line"]
    m = re.search(r"来源：(.+?)\s*｜", ml)
    if m:
        item["source"] = m.group(1).strip()
    m = re.search(r"词数：(\d+)", ml)
    if m:
        item["word_count"] = int(m.group(1))
    m = re.search(r"难度：(\S+)", ml)
    if m:
        item["level"] = m.group(1).strip()
    m = re.search(r"原文：(\S+)", ml)
    if m:
        item["url"] = m.group(1).strip()

    return item


def export(cfg: dict, out_root: Path) -> int:
    """扫描 output/ 下所有 Markdown，汇总成 docs/ 下的 JSON。"""
    app = cfg.get("app") or {}
    if not app.get("enabled", False):
        return 0

    docs = Path(app.get("dir", "docs"))
    docs.mkdir(parents=True, exist_ok=True)
    keep_days = int(app.get("keep_days", 90) or 0)
    cutoff = dt.date.today() - dt.timedelta(days=keep_days) if keep_days else None

    items: list[dict] = []
    vocab_bank: dict[str, dict] = {}

    for md in sorted(out_root.rglob("*.md")):
        name = md.name
        if name.endswith("-selftest.md"):
            continue
        m = re.match(r"(\d{4}-\d{2}-\d{2})-(.+)\.md$", name)
        if not m:
            continue
        date, slug = m.group(1), m.group(2)
        try:
            if cutoff and dt.date.fromisoformat(date) < cutoff:
                continue
        except ValueError:
            continue

        item = build_item(md, slug, date)
        if not item:
            continue

        item["title_zh"] = item.get("title_zh") or slug.replace("-", " ").title()
        items.append(item)

        for v in item["vocab"]:
            w = (v.get("word") or "").strip().lower()
            if not w:
                continue
            if w in vocab_bank:
                vocab_bank[w]["count"] += 1
                vocab_bank[w]["dates"].append(date)
            else:
                vocab_bank[w] = {
                    "word": v.get("word", ""), "pos": v.get("pos", ""),
                    "phonetic": v.get("phonetic", ""),
                    "meaning_zh": v.get("meaning_zh", ""),
                    "count": 1, "dates": [date],
                }

    items.sort(key=lambda x: x["date"], reverse=True)
    bank = sorted(vocab_bank.values(), key=lambda x: (-x["count"], x["word"]))

    (docs / "index.json").write_text(
        json.dumps({
            "updated": dt.datetime.now().isoformat(timespec="seconds"),
            "count": len(items),
            "items": [
                {k: v for k, v in it.items() if k in
                 ("id", "date", "title_zh", "summary", "source", "level",
                  "word_count", "url", "vocab")}
                for it in items[: int(app.get("index_limit", 60))]
            ],
        }, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    (docs / "vocab.json").write_text(
        json.dumps({"updated": dt.datetime.now().isoformat(timespec="seconds"),
                    "count": len(bank), "vocab": bank},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    day_dir = docs / "daily"
    day_dir.mkdir(parents=True, exist_ok=True)
    for it in items:
        (day_dir / f"{it['date']}-{it['slug']}.json").write_text(
            json.dumps(it, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    print(f"  [导出] docs/index.json（{len(items)} 篇）、"
          f"docs/vocab.json（{len(bank)} 词）、docs/daily/*.json")
    return len(items)


def _title_from_md(md_path: Path) -> str:
    """中文标题是正文里第一行加粗（渲染时写在 meta 行之前）。"""
    try:
        text = md_path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return ""
    head = text.split("## ", 1)[0]
    m = re.search(r"^\*\*(.+?)\*\*\s*$", head, re.M)
    return m.group(1).strip() if m else ""
