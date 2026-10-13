"""外刊精读 · 主流程

用法：
  python main.py                 正常跑：抓取 → 精读 → 归档 → 发邮件
  python main.py --no-email      不发电邮，只生成归档
  python main.py --count 2       今天精读 2 篇
  python main.py --url <链接>     指定文章（调试用）
  python main.py --selftest      自检：不联网、不调模型，验证渲染链路
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

from src import analyze as analyze_mod
from src import anki as anki_mod
from src import extract, fetch, mailer, render, wechat
from src import export_app
from src.config import ROOT, load_config

STATE_DIR = ROOT / "state"
SEEN_FILE = STATE_DIR / "seen.json"
MAX_SEEN = 3000
BJ = dt.timezone(dt.timedelta(hours=8))


# ---------------------------------------------------------------- 状态

def load_seen() -> set[str]:
    if not SEEN_FILE.exists():
        return set()
    try:
        return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")).get("keys", []))
    except Exception:  # noqa: BLE001
        return set()


def save_seen(seen: set[str]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    keys = list(seen)[-MAX_SEEN:]
    SEEN_FILE.write_text(
        json.dumps({"keys": keys, "updated": dt.datetime.now(BJ).isoformat(timespec="seconds")},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def prune_output(out_dir: Path, keep_days: int) -> None:
    if keep_days <= 0:
        return
    cutoff = dt.date.today() - dt.timedelta(days=keep_days)
    removed = 0
    for f in out_dir.rglob("*.md"):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", f.name)
        if not m:
            continue
        try:
            if dt.date.fromisoformat(m.group(1)) < cutoff:
                f.unlink()
                removed += 1
        except ValueError:
            continue
    if removed:
        print(f"  [归档清理] 删除 {removed} 份超过 {keep_days} 天的旧文件")


def slugify(title: str, fallback: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
    return (s[:40].strip("-") or fallback)


# ---------------------------------------------------------------- 自检

SAMPLE_BODY = (
    "The world's largest container shipping companies are rerouting their fleets "
    "around southern Africa, adding more than a week to journeys between Asia and Europe.\n\n"
    "Executives say the detour, prompted by attacks on vessels in the Red Sea, is likely to "
    "persist well into next year, pushing up freight rates and complicating efforts to tame "
    "inflation.\n\n"
    "For manufacturers that rely on just-in-time delivery, the consequences are immediate. "
    "Some have been forced to hold more stock, tying up capital that would otherwise fund "
    "expansion."
)

SAMPLE_RESULT = {
    "title_zh": "红海改道推高运费，全球供应链再度承压",
    "level": "B2",
    "word_count": 88,
    "summary_zh": "集装箱航运巨头集体绕行非洲南端，亚欧航线延长一周以上。高管预计这一局面将持续到明年，运费上涨给通胀调控增添变数。对依赖准时制交付的制造商而言，影响立刻显现——被迫提高库存，占用本可用于扩张的资金。",
    "vocab": [
        {"word": "reroute", "pos": "v.", "phonetic": "/ˌriːˈruːt/",
         "meaning_zh": "改变（航线、路线）",
         "example_en": "The companies are rerouting their fleets around southern Africa.",
         "example_zh": "这些公司正让船队绕行非洲南部。"},
        {"word": "detour", "pos": "n.", "phonetic": "/ˈdiːtʊə(r)/",
         "meaning_zh": "绕行，迂回路线",
         "example_en": "The detour is likely to persist well into next year.",
         "example_zh": "这种绕行很可能持续到明年较晚时候。"},
        {"word": "just-in-time", "pos": "adj.", "phonetic": "/ˌdʒʌst ɪn ˈtaɪm/",
         "meaning_zh": "准时制的（零库存生产）",
         "example_en": "For manufacturers that rely on just-in-time delivery, the consequences are immediate.",
         "example_zh": "对依赖准时制交付的制造商来说，后果立竿见影。"},
    ],
    "grammar": [
        {"sentence": "Executives say the detour, prompted by attacks on vessels in the Red Sea, is likely to persist well into next year.",
         "point": "过去分词短语作插入语（插入定语）",
         "explain_zh": "prompted by... 是过去分词短语，插在主语 the detour 和谓语 is likely to 之间作后置定语，相当于 which was prompted by...。外刊常用这种写法压缩篇幅，读的时候要把插入部分暂时摘出去，先抓主干 Executives say the detour is likely to persist。"},
        {"sentence": "Some have been forced to hold more stock, tying up capital that would otherwise fund expansion.",
         "point": "现在分词作结果状语 + that 引导定语从句",
         "explain_zh": "tying up capital 是现在分词短语，表示前面动作带来的伴随结果；that would otherwise fund expansion 是定语从句修饰 capital，otherwise 暗示一种「本来会……却因此没有发生」的虚拟对比，是外刊表达因果代价的常见套路。"},
    ],
    "translation": [
        {"en": "The world's largest container shipping companies are rerouting their fleets around southern Africa, adding more than a week to journeys between Asia and Europe.",
         "zh": "全球最大的集装箱航运公司正让船队绕行非洲南部，使亚欧之间的航程增加了一周以上。"},
        {"en": "Executives say the detour, prompted by attacks on vessels in the Red Sea, is likely to persist well into next year, pushing up freight rates and complicating efforts to tame inflation.",
         "zh": "高管们表示，因红海船只遇袭而引发的绕行，很可能持续到明年较晚时候，这将推高运费，并使遏制通胀的努力更加复杂。"},
        {"en": "For manufacturers that rely on just-in-time delivery, the consequences are immediate.",
         "zh": "对于依赖准时制交付的制造商而言，后果立刻显现。"},
        {"en": "Some have been forced to hold more stock, tying up capital that would otherwise fund expansion.",
         "zh": "一些企业被迫持有更多库存，占用了原本可用于扩张的资金。"},
    ],
    "questions": [
        {"q": "What is the immediate cause of the rerouting?",
         "a": "针对红海船只的袭击（attacks on vessels in the Red Sea）。"},
        {"q": "According to the article, why is the detour bad for manufacturers that rely on just-in-time delivery?",
         "a": "航程延长使准时制交付难以维持，企业被迫增加库存，占用了原本可以用于扩张的资金。"},
        {"q": "What is the author's overall tone towards the situation?",
         "a": "客观但偏忧虑：作者把它描述为一个会持续、并给通胀调控增加难度的问题。"},
    ],
}


def selftest(cfg: dict) -> int:
    print("=== 自检模式：不联网、不调用大模型 ===")
    today = dt.datetime.now(BJ).strftime("%Y-%m-%d")
    meta = {
        "date": today,
        "source": "自检样例",
        "url": "https://example.com/sample",
        "word_count": fetch.word_count(SAMPLE_BODY),
        "body": SAMPLE_BODY,
        "keep_en_article": True,
    }
    data = dict(SAMPLE_RESULT)
    data["word_count"] = meta["word_count"]

    md = render.render_markdown(data, meta)
    html = render.render_html(data, meta)

    # 自检产物写到 .selftest/（已在 .gitignore 里），不污染 output/ 归档
    out_dir = ROOT / ".selftest"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{today}-selftest.md"
    html_path = out_dir / f"{today}-selftest.html"
    md_path.write_text(md, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    print(f"  Markdown 已写出：{md_path}")
    print(f"  HTML 已写出：{html_path}")

    if cfg["output"].get("anki", False):
        a = anki_mod.build(cfg, data, meta, out_dir)
        if a:
            a.unlink()  # 自检不留下卡片包

    # 顺手校验一下 JSON 解析的兜底逻辑
    from src.analyze import _parse_json
    assert _parse_json('```json\n{"a": 1}\n```')["a"] == 1
    assert _parse_json('好的，结果如下：{"a": 2} 以上。')["a"] == 2
    print("  JSON 兜底解析：通过")
    print("=== 自检完成 ===")
    return 0


# ---------------------------------------------------------------- 主流程

def run(cfg: dict, args) -> int:
    today = dt.datetime.now(BJ).strftime("%Y-%m-%d")
    out_root = ROOT / cfg["output"].get("dir", "output")
    day_dir = out_root / today[:7]
    keep_en = cfg["study"].get("keep_en_article", True)

    seen = load_seen()
    ready: dict[int, dict] = {}      # 序号 → 现成的精读结果

    # ---- 离线模式：直接从 JSON 读原文（可含现成精读结果）----
    if args.from_json:
        items = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        articles = [
            (
                fetch.Candidate(
                    title=it.get("title", ""), link=it.get("url", ""),
                    source=it.get("source", ""), summary="",
                ),
                it.get("body", ""),
                it.get("word_count") or fetch.word_count(it.get("body", "")),
            )
            for it in items
        ]
        for i, it in enumerate(items):
            if it.get("analysis"):
                ready[i] = it["analysis"]
        print(f"[离线] 从 {args.from_json} 读到 {len(articles)} 篇，"
              f"其中 {len(ready)} 篇自带精读结果")
    else:
        # ---- 1. 抓取 ----
        want = int(cfg["selection"].get("count", 1))
        print("[1/5] 抓取 RSS ...")
        if args.url:
            candidates = [
                fetch.Candidate(title=args.url, link=args.url, source="手动指定", summary="")
            ]
        else:
            pool = fetch.collect(cfg, seen)
            print(f"  候选文章：{len(pool)} 篇")
            if not pool:
                print("  没有新文章可读，今天跳过。")
                return 0
            # 多挑一批当缓冲：正文长度要抓下来才知道，抓完再筛。
            # 有些站点正文会 403、有些抓下来是广播转写稿，所以缓冲给足，
            # 并放宽同源上限，保证一天里总能捞到一篇能用的。
            candidates = fetch.pick(pool, cfg, want=want * 8 + 8, per_source=3)
        print(f"  待筛候选：{len(candidates)} 篇（目标 {want} 篇）")

        # ---- 2. 抽取正文 ----
        print("[2/5] 抽取正文 ...")
        articles = []
        for c in candidates:
            if len(articles) >= want:
                break
            body = extract.extract(c.link, c.summary, title=c.title)
            wc = fetch.word_count(body)
            ok, why = fetch.usable(body, cfg)
            if not ok:
                print(f"  [跳过] {why}：{c.title[:55]}")
                seen.add(c.key)
                continue
            print(f"  ✓ {wc} 词 · {c.source} · {c.title[:60]}")
            articles.append((c, body, wc))

    if not articles:
        save_seen(seen)
        print("  今天没有符合长度要求的文章，跳过。")
        return 0

    if args.dump:
        dump_path = Path(args.dump)
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        dump_path.write_text(
            json.dumps(
                [
                    {"source": c.source, "title": c.title, "url": c.link,
                     "word_count": wc, "body": body}
                    for c, body, wc in articles
                ],
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
        print(f"  原文已存到：{dump_path}（未调用大模型）")
        return 0

    # ---- 3. 精读 ----
    print("[3/5] 生成精读材料 ...")
    day_dir.mkdir(parents=True, exist_ok=True)
    for i, (c, body, wc) in enumerate(articles):
        data = ready.get(i)
        if data is None:
            try:
                data = analyze_mod.analyze(cfg, c.source, c.title, c.link, body)
            except Exception as exc:  # noqa: BLE001
                print(f"  [失败] 精读出错：{type(exc).__name__} {exc}")
                continue
        else:
            print("  [离线] 使用 JSON 里的现成精读结果")

        meta = {
            "date": today,
            "source": c.source,
            "url": c.link,
            "word_count": wc,
            "body": body,
            "keep_en_article": keep_en,
            "title": c.title,
        }

        # ---- 4. 写出 ----
        md = render.render_markdown(data, meta)
        html = render.render_html(data, meta)
        stem = f"{today}-{slugify(c.title, c.key)}"
        (day_dir / f"{stem}.md").write_text(md, encoding="utf-8")
        (day_dir / f"{stem}.html").write_text(html, encoding="utf-8")
        print(f"  [归档] {day_dir / (stem + '.md')}")

        if cfg["output"].get("anki", False):
            anki_mod.build(cfg, data, meta, out_root / "anki")

        # ---- 5. 推送 ----
        if cfg["email"].get("enabled", True) and not args.no_email:
            prefix = cfg["email"].get("subject_prefix", "【外刊精读】")
            subject = f"{prefix}{data.get('title_zh') or c.title}（{today}）"
            mailer.send(cfg, subject, html)
        else:
            print("  [跳过邮件] 已关闭或指定 --no-email")

        if not args.no_push:
            wechat.push_all(cfg, data, meta)

        if not args.from_json:
            seen.add(c.key)

    save_seen(seen)
    prune_output(out_root, int(cfg["output"].get("keep_days", 0)))

    # ---- 6. 导出给小程序 / 网页前端 ----
    print("[6/6] 导出前端 JSON ...")
    if args.no_push:
        print("  [跳过导出] 指定了 --no-push")
    else:
        export_app.export(cfg, out_root)

    print("完成。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="外刊精读 · 每日自动生成精读材料")
    parser.add_argument("--config", default=None, help="配置文件路径")
    parser.add_argument("--count", type=int, default=None, help="今天精读几篇，覆盖 config")
    parser.add_argument("--url", default=None, help="指定一篇文章链接（调试用）")
    parser.add_argument("--no-email", action="store_true", help="不发送邮件")
    parser.add_argument("--no-push", action="store_true",
                        help="不推送微信、不导出前端 JSON")
    parser.add_argument("--selftest", action="store_true", help="离线自检，验证渲染链路")
    parser.add_argument("--dump", default=None,
                        help="把抓到的原文存成 JSON 后退出，不调用大模型（先看看抓到了什么）")
    parser.add_argument("--from-json", default=None,
                        help="跳过抓取，直接用现成的精读 JSON 渲染（离线调试用）")
    args = parser.parse_args()

    if args.selftest:
        # 自检不需要 API Key，先塞个占位符免得被 config 拦下
        import os
        os.environ.setdefault("LLM_API_KEY", "selftest")
        cfg = load_config(args.config)
        if args.count:
            cfg["selection"]["count"] = args.count
        return selftest(cfg)

    cfg = load_config(args.config)
    if args.count:
        cfg["selection"]["count"] = args.count
    return run(cfg, args)


if __name__ == "__main__":
    sys.exit(main())
