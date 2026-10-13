"""把精读结果渲染成 Markdown（归档用）和 HTML（邮件用）。"""
from __future__ import annotations

import html as _html

from .extract import paragraphs

CN_NUM = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]


def _sec(i: int, title: str) -> str:
    return f"## {CN_NUM[i]}、{title}"


def render_markdown(data: dict, meta: dict) -> str:
    lines: list[str] = []
    lines.append(f"# 外刊精读 · {meta['date']}")
    lines.append("")
    lines.append(
        f"> 来源：{meta['source']} ｜ 难度：{data.get('level', '—')} "
        f"｜ 词数：{meta['word_count']}"
    )
    lines.append(f"> 原文：{meta['url']}")
    lines.append("")

    i = 0
    if data.get("summary_zh"):
        lines += [_sec(i, "导读"), "", data["summary_zh"].strip(), ""]
        i += 1

    if meta.get("body") and meta.get("keep_en_article", True):
        lines += [_sec(i, "原文"), ""]
        for p in paragraphs(meta["body"]):
            lines += [p, ""]
        i += 1

    if data.get("translation"):
        lines += [_sec(i, "逐段翻译"), ""]
        for idx, seg in enumerate(data["translation"], 1):
            lines.append(f"**{idx}.** {str(seg.get('en', '')).strip()}")
            lines.append("")
            lines.append(str(seg.get("zh", "")).strip())
            lines.append("")
        i += 1

    if data.get("vocab"):
        lines += [_sec(i, "生词表"), "", "| 词 | 词性 | 音标 | 释义 |", "| --- | --- | --- | --- |"]
        for v in data["vocab"]:
            lines.append(
                f"| {v.get('word', '')} | {v.get('pos', '')} | "
                f"{v.get('phonetic', '')} | {v.get('meaning_zh', '')} |"
            )
        lines.append("")
        for v in data["vocab"]:
            lines.append(f"- **{v.get('word', '')}** {v.get('meaning_zh', '')}")
            lines.append(f"  - {v.get('example_en', '')}")
            lines.append(f"  - {v.get('example_zh', '')}")
        lines.append("")
        i += 1

    if data.get("grammar"):
        lines += [_sec(i, "长难句拆解"), ""]
        for idx, g in enumerate(data["grammar"], 1):
            lines.append(f"**{idx}）{g.get('sentence', '')}**")
            lines.append("")
            lines.append(f"- 结构：{g.get('point', '')}")
            lines.append(f"- 讲解：{g.get('explain_zh', '')}")
            lines.append("")
        i += 1

    if data.get("questions"):
        lines += [_sec(i, "理解题"), ""]
        for idx, q in enumerate(data["questions"], 1):
            lines.append(f"**{idx}.** {q.get('q', '')}")
            lines.append("")
            lines.append(f"> 参考答案：{q.get('a', '')}")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*由「外刊精读」自动生成 · 每天一篇，读原文，也读世界*")
    lines.append("")
    return "\n".join(lines)


def _esc(text) -> str:
    return _html.escape(str(text or ""))


def render_html(data: dict, meta: dict) -> str:
    """邮件用的 HTML。全部内联样式，兼容各家邮箱客户端。"""
    body_font = "font-family:-apple-system,'Segoe UI','Microsoft YaHei',sans-serif;"
    parts: list[str] = []
    parts.append(
        '<div style="max-width:680px;margin:0 auto;padding:8px 4px;color:#1f2328;'
        f'font-size:16px;line-height:1.8;{body_font}">'
    )
    parts.append(
        f'<h1 style="font-size:21px;margin:0 0 8px;">外刊精读 · {_esc(meta["date"])}</h1>'
    )
    parts.append(
        '<p style="margin:0 0 4px;color:#57606a;font-size:14px;">'
        f'来源：{_esc(meta["source"])} ｜ 难度：{_esc(data.get("level", "—"))} '
        f'｜ 词数：{_esc(meta["word_count"])}</p>'
    )
    parts.append(
        '<p style="margin:0 0 24px;font-size:14px;">'
        f'<a href="{_esc(meta["url"])}" style="color:#185fa5;">查看原文 →</a></p>'
    )

    if data.get("summary_zh"):
        parts.append(
            '<div style="background:#f1efe8;border-radius:12px;padding:16px 18px;margin-bottom:28px;">'
            '<p style="margin:0 0 6px;font-size:13px;color:#57606a;font-weight:500;">导读</p>'
            f'<p style="margin:0;">{_esc(data["summary_zh"])}</p></div>'
        )

    def section(title: str) -> None:
        parts.append(
            '<h2 style="font-size:17px;margin:32px 0 12px;padding-bottom:6px;'
            f'border-bottom:1px solid #e3e2dd;">{_esc(title)}</h2>'
        )

    if meta.get("body") and meta.get("keep_en_article", True):
        section("原文")
        for p in paragraphs(meta["body"]):
            parts.append(
                f'<p style="margin:0 0 14px;color:#24292f;">{_esc(p)}</p>'
            )

    if data.get("translation"):
        section("逐段翻译")
        for idx, seg in enumerate(data["translation"], 1):
            parts.append(
                '<div style="margin:0 0 18px;padding-left:12px;border-left:2px solid #d3d1c7;">'
                f'<p style="margin:0 0 6px;color:#57606a;font-size:15px;">{idx}. {_esc(seg.get("en"))}</p>'
                f'<p style="margin:0;">{_esc(seg.get("zh"))}</p></div>'
            )

    if data.get("vocab"):
        section("生词表")
        parts.append(
            '<table style="width:100%;border-collapse:collapse;font-size:15px;'
            'table-layout:fixed;">'
            '<tr style="background:#f1efe8;">'
            '<th style="text-align:left;padding:8px 10px;width:24%;">词</th>'
            '<th style="text-align:left;padding:8px 10px;width:11%;">词性</th>'
            '<th style="text-align:left;padding:8px 10px;width:21%;">音标</th>'
            '<th style="text-align:left;padding:8px 10px;">释义</th></tr>'
        )
        for v in data["vocab"]:
            parts.append(
                '<tr style="border-bottom:1px solid #eceae4;">'
                f'<td style="padding:8px 10px;font-weight:500;">{_esc(v.get("word"))}</td>'
                f'<td style="padding:8px 10px;color:#57606a;">{_esc(v.get("pos"))}</td>'
                f'<td style="padding:8px 10px;color:#57606a;">{_esc(v.get("phonetic"))}</td>'
                f'<td style="padding:8px 10px;">{_esc(v.get("meaning_zh"))}</td></tr>'
            )
        parts.append("</table>")

        parts.append('<div style="margin-top:18px;">')
        for v in data["vocab"]:
            parts.append(
                '<div style="margin:0 0 12px;padding:10px 12px;background:#f7f6f2;'
                'border-radius:8px;">'
                f'<p style="margin:0 0 4px;font-weight:500;">{_esc(v.get("word"))} '
                f'<span style="font-weight:400;color:#57606a;">{_esc(v.get("meaning_zh"))}</span></p>'
                f'<p style="margin:0;color:#57606a;font-size:15px;">{_esc(v.get("example_en"))}</p>'
                f'<p style="margin:0;color:#8b949e;font-size:14px;">{_esc(v.get("example_zh"))}</p>'
                "</div>"
            )
        parts.append("</div>")

    if data.get("grammar"):
        section("长难句拆解")
        for idx, g in enumerate(data["grammar"], 1):
            parts.append(
                '<div style="margin:0 0 18px;">'
                f'<p style="margin:0 0 6px;font-weight:500;">{idx}. {_esc(g.get("sentence"))}</p>'
                '<p style="margin:0 0 4px;font-size:15px;"><span style="color:#57606a;">结构：</span>'
                f'{_esc(g.get("point"))}</p>'
                '<p style="margin:0;font-size:15px;"><span style="color:#57606a;">讲解：</span>'
                f'{_esc(g.get("explain_zh"))}</p></div>'
            )

    if data.get("questions"):
        section("理解题")
        for idx, q in enumerate(data["questions"], 1):
            parts.append(
                '<div style="margin:0 0 16px;">'
                f'<p style="margin:0 0 6px;">{idx}. {_esc(q.get("q"))}</p>'
                '<p style="margin:0;color:#57606a;font-size:15px;">参考答案：'
                f'{_esc(q.get("a"))}</p></div>'
            )

    parts.append(
        '<p style="margin:36px 0 0;padding-top:16px;border-top:1px solid #e3e2dd;'
        'color:#8b949e;font-size:13px;">由「外刊精读」自动生成 · 每天一篇，读原文，也读世界</p>'
    )
    parts.append("</div>")
    return "".join(parts)
