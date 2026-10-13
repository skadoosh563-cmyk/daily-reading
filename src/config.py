"""外刊精读 —— 配置加载。"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """本地跑的时候读一下 .env；在 Actions 上这些值来自 Secrets。"""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        # 已存在的真实环境变量优先级更高，不覆盖
        if value and key not in os.environ:
            os.environ[key] = value


def load_config(path: str | Path | None = None) -> dict:
    _load_dotenv()
    cfg_path = Path(path) if path else ROOT / "config.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    cfg.setdefault("sources", [])
    cfg.setdefault("selection", {})
    cfg.setdefault("llm", {})
    cfg.setdefault("study", {})
    cfg.setdefault("output", {})
    cfg.setdefault("email", {})

    # 环境变量允许覆盖 LLM 配置，方便临时换模型
    cfg["llm"]["api_key"] = os.environ.get("LLM_API_KEY", "").strip()
    if os.environ.get("LLM_BASE_URL"):
        cfg["llm"]["base_url"] = os.environ["LLM_BASE_URL"].strip()
    if os.environ.get("LLM_MODEL"):
        cfg["llm"]["model"] = os.environ["LLM_MODEL"].strip()

    if not cfg["llm"].get("api_key"):
        raise SystemExit(
            "没有读到 LLM_API_KEY。\n"
            "  本地：把 .env.example 复制成 .env 并填入 API Key\n"
            "  Actions：在仓库 Settings → Secrets and variables → Actions 里加 LLM_API_KEY"
        )
    return cfg


def enabled_sources(cfg: dict) -> list[dict]:
    return [s for s in cfg["sources"] if s.get("url") and s.get("enabled", True)]
