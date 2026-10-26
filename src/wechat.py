"""把每日精读推送到微信。

提供三个通道，各取所需（可以同时开）：

1. Server 酱（方糖）——最省事
   个人主体可用，免费额度够日常使用。关注公众号拿到 SendKey，
   内容会以「微信服务号模板消息」的形式推给你。
   注册：https://sct.ftqq.com/

2. 企业微信群机器人——免费、无条数限制，最推荐
   自己建一个企业微信（个人也能注册），拉个只有自己的群，
   群里添加「群机器人」，把 Webhook 地址抄过来即可。
   注意：企业微信可以和个人微信互通，消息能到微信里看。

3. 自定义 Webhook——钉钉、飞书、Bark、ntfy 等
   凡是「POST 一个 JSON 就能发通知」的服务都能接。

所有 token / webhook 都放环境变量或 GitHub Secrets，不要写进代码。
"""
from __future__ import annotations

import json
import os
import re

import requests

TIMEOUT = 20


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_digest_text(data: dict, meta: dict) -> str:
    """推送到微信的纯文本摘要。

    微信通道不适合推长文（公众号模板消息有长度限制，
    群机器人的 markdown 也不适合塞整篇翻译），所以只推
    「导读 + 生词表 + 原文链接」，完整内容在仓库和邮件里看。
    """
    lines: list[str] = []
    title = data.get("title_zh") or meta.get("title") or "今日外刊"
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"来源：{meta.get('source', '')} ｜ 难度：{data.get('level', '—')} "
                 f"｜ 词数：{meta.get('word_count', '')}")
    lines.append("")

    if data.get("summary_zh"):
        lines.append("**导读**")
        lines.append(data["summary_zh"].strip())
        lines.append("")

    vocab = data.get("vocab") or []
    if vocab:
        lines.append(f"**今日生词（{len(vocab)}）**")
        for v in vocab:
            word = v.get("word", "")
            meaning = v.get("meaning_zh", "")
            lines.append(f"- {word} — {meaning}")
        lines.append("")

    if data.get("questions"):
        lines.append("**理解题**")
        for i, q in enumerate(data["questions"], 1):
            lines.append(f"{i}. {q.get('q', '')}")
        lines.append("")

    lines.append(f"[读原文]({meta.get('url', '')})")
    return "\n".join(lines)


def _serverchan_url(key: str) -> str:
    """按 key 的版本决定推送地址。

    旧版 SendKey 是 SCT 开头，走 sctapi.ftqq.com；
    新版「Server酱³」是 sctp 开头，uid 就夹在 "sctp" 和 "t" 之间，
    要走独立的 {uid}.push.ft07.com 域名，用错地址会直接 404。
    """
    m = re.match(r"sctp(\d+)t", key)
    if m:
        return f"https://{m.group(1)}.push.ft07.com/send/{key}.send"
    return f"https://sctapi.ftqq.com/{key}.send"


def push_serverchan(title: str, body: str) -> bool:
    """Server 酱：https://sct.ftqq.com/"""
    key = os.environ.get("SERVERCHAN_KEY", "").strip()
    if not key:
        return False
    url = _serverchan_url(key)
    try:
        resp = requests.post(
            url,
            data={"title": _truncate(title, 100), "desp": body},
            timeout=TIMEOUT,
        )
        # 和 analyze.py 一样，不依赖响应头的 charset
        data = json.loads(resp.content.decode("utf-8", "replace"))
        ok = data.get("code") in (0, 200)
        msg = data.get("message") or data.get("info") or data
        print(f"  [Server酱] {'已推送' if ok else '失败：' + str(msg)}")
        return ok
    except Exception as exc:  # noqa: BLE001
        print(f"  [Server酱] 推送出错：{type(exc).__name__} {exc}")
        return False


def push_wecom(title: str, body: str) -> bool:
    """企业微信群机器人。Webhook 形如
    https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxx
    """
    hook = os.environ.get("WECOM_WEBHOOK", "").strip()
    if not hook:
        return False
    payload = {
        "msgtype": "markdown",
        "markdown": {"content": _truncate(f"# {title}\n{body}", 4000)},
    }
    return _post_json(hook, payload, "企业微信")


def push_custom(title: str, body: str) -> bool:
    """自定义 Webhook：钉钉 / 飞书 / Bark / ntfy 等。"""
    hook = os.environ.get("CUSTOM_WEBHOOK", "").strip()
    if not hook:
        return False
    payload = {"title": title, "text": body, "content": body}
    return _post_json(hook, payload, "自定义Webhook")


def _post_json(url: str, payload: dict, label: str) -> bool:
    try:
        resp = requests.post(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, timeout=TIMEOUT,
        )
        ok = resp.status_code < 300
        print(f"  [{label}] {'已推送' if ok else f'失败：HTTP {resp.status_code}'}")
        return ok
    except Exception as exc:  # noqa: BLE001
        print(f"  [{label}] 推送出错：{type(exc).__name__} {exc}")
        return False


def push_all(cfg: dict, data: dict, meta: dict) -> int:
    """按配置把内容推到所有已开启的微信通道，返回成功数量。"""
    wx = cfg.get("wechat") or {}
    if not wx.get("enabled", False):
        return 0

    title = f"{wx.get('subject_prefix', '【外刊精读】')}{data.get('title_zh') or meta.get('title', '')}"
    body = build_digest_text(data, meta)

    sent = 0
    if wx.get("serverchan", True):
        sent += bool(push_serverchan(title, body))
    if wx.get("wecom", True):
        sent += bool(push_wecom(title, body))
    if wx.get("custom", True):
        sent += bool(push_custom(title, body))

    if sent == 0:
        print("  [微信推送] 没有可用的通道（未配置任何 token / webhook）")
    return sent
