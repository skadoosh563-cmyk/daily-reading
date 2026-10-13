"""把当天的生词生成 Anki 卡片包（.apkg）。

这是整个项目里最容易被跳过、但最影响效果的一环：
每天读一篇不难，难的是记住。生成 apkg 后导入 Anki，
按遗忘曲线复习，才算把外刊真正读进脑子里。
"""
from __future__ import annotations

import re
from pathlib import Path

DECK_NAME = "外刊精读"


def _basic_model():
    import genanki

    model = genanki.Model(
        1607392319,
        "外刊精读-单词卡",
        fields=[
            {"name": "Word"},
            {"name": "Phonetic"},
            {"name": "Meaning"},
            {"name": "ExampleEN"},
            {"name": "ExampleZH"},
            {"name": "Source"},
        ],
        templates=[
            {
                "name": "卡片 1",
                "qfmt": "<div class='w'>{{Word}}</div><div class='p'>{{Phonetic}}</div>",
                "afmt": (
                    "{{FrontSide}}<hr id=answer>"
                    "<div class='m'>{{Meaning}}</div>"
                    "<div class='e'>{{ExampleEN}}</div>"
                    "<div class='z'>{{ExampleZH}}</div>"
                    "<div class='s'>{{Source}}</div>"
                ),
            }
        ],
        css="""
        .card { font-family: -apple-system, "Microsoft YaHei", sans-serif;
                font-size: 19px; color: #1f2328; text-align: left; padding: 8px 4px; }
        .w { font-size: 26px; font-weight: 600; }
        .p { color: #57606a; font-size: 15px; margin-top: 2px; }
        .m { margin-top: 6px; }
        .e { margin-top: 12px; color: #24292f; }
        .z { color: #8b949e; font-size: 16px; }
        .s { margin-top: 14px; color: #b0aea8; font-size: 13px; }
        """,
    )
    return model


def build(cfg: dict, data: dict, meta: dict, out_dir: Path) -> Path | None:
    """生成 .apkg，返回文件路径；失败返回 None。"""
    vocab = data.get("vocab") or []
    if not vocab:
        return None
    try:
        import genanki
    except ImportError:
        print("  [跳过 Anki] 没装 genanki，执行 pip install genanki 后可用")
        return None

    try:
        deck_id = int(re.sub(r"\D", "", meta["date"])[:8] or "20260101")
        deck = genanki.Deck(deck_id, DECK_NAME)
        model = _basic_model()

        for v in vocab:
            note = genanki.Note(
                model=model,
                fields=[
                    str(v.get("word", "")),
                    str(v.get("phonetic", "")),
                    str(v.get("meaning_zh", "")),
                    str(v.get("example_en", "")),
                    str(v.get("example_zh", "")),
                    f"{meta['source']} · {meta['date']}",
                ],
                tags=["外刊精读", meta["date"][:7]],
            )
            deck.add_note(note)

        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"外刊精读-{meta['date']}.apkg"
        genanki.Package(deck).write_to_file(str(path))
        print(f"  [Anki 卡片] {len(vocab)} 张 → {path.name}")
        return path
    except Exception as exc:  # noqa: BLE001
        print(f"  [跳过 Anki] 生成失败：{type(exc).__name__} {exc}")
        return None
