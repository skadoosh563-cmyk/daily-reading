# 外刊精读

每天早上自动给你一篇外刊精读：**导读 → 原文 → 逐段翻译 → 生词表 → 长难句拆解 → 理解题**，
邮件直达，同时生成 Anki 卡片包。

零服务器、零成本（公开仓库 Actions 免费），部署一次之后每天自动运行。

---

## 它每天做了什么

```
抓取 RSS  →  挑选一篇长度合适的  →  抓取正文全文  →  调用大模型精读
   ↓
生成 Markdown 归档 + HTML 邮件
   ↓
邮件推送 + 生成 Anki 卡片(.apkg) + 提交回仓库
```

去重记录存在 `state/seen.json`，同一篇文章不会被推第二次。

---

## 部署：五步

### 1. 建仓库

在 GitHub 上新建一个仓库（公开仓库 Actions 不限时长），把本项目所有文件传上去。
最省事的做法：网页端上传，或用命令行——

```bash
git init
git add .
git commit -m "init: 外刊精读"
git branch -M main
git remote add origin https://github.com/你的用户名/外刊精读.git
git push -u origin main
```

### 2. 拿一个大模型 API Key

任选一家，都兼容 OpenAI 接口：

| 服务商 | base_url | 推荐模型 |
| --- | --- | --- |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 月之暗面 | `https://api.moonshot.cn/v1` | `moonshot-v1-32k` |
| 智谱 | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 硅基流动 | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-72B-Instruct` |

拿到 Key 之后，改 `config.yaml` 里的 `llm.base_url` 和 `llm.model`。

### 3. 配邮件（不想收邮件可以跳过）

去邮箱设置里开 SMTP 并拿到**授权码**（不是登录密码）。
QQ 邮箱路径：设置 → 账户 → 开启 SMTP 服务 → 生成授权码。

### 4. 填 Secrets

仓库 → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`：

| 名称 | 说明 | 必填 |
| --- | --- | --- |
| `LLM_API_KEY` | 大模型 API Key | ✅ |
| `SMTP_SENDER` | 发件邮箱 | 可选 |
| `SMTP_PASSWORD` | SMTP 授权码 | 可选 |
| `SMTP_RECEIVER` | 收件邮箱，多个用逗号隔开 | 可选 |

### 5. 开权限并手动跑一次

- `Settings` → `Actions` → `General` → `Workflow permissions` 选 **Read and write permissions**
  （不然归档推不回去，任务会失败）
- `Actions` 标签页 → 左侧「每日外刊精读」→ `Run workflow`

看到邮件和仓库里多出 `output/` 目录，就成功了。之后每天北京时间早上 7 点自动跑。

---

## 本地测试

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # 填 LLM_API_KEY 和邮箱授权码

python main.py --selftest        # 自检：不联网不调模型，验证渲染
python main.py --no-email        # 真跑一次但不发邮件
python main.py --url <文章链接>   # 指定一篇文章调试
```

---

## 日常调整

**换素材源**：编辑 `config.yaml` 的 `sources`，加 `name` / `url` 两行即可；
不想要某个源，加 `enabled: false`。

**控制难度和长度**：`selection.min_words` / `max_words` 控制文章长度，
`study.level` 控制讲解深浅（A2 / B1 / B2 / C1）。

**每天多读几篇**：`selection.count: 2`。

**不想收邮件只要归档**：`email.enabled: false`。

**关掉 Anki 卡片**：`output.anki: false`。

---

## 会用到的坑（提前告诉你）

| 坑 | 说明 |
| --- | --- |
| cron 是 UTC | 想北京时间 7 点跑，写 `0 23 * * *`（前一天 UTC 23 点） |
| 60 天不活动会停 | 公开仓库长期无提交，定时任务会被 GitHub 自动禁用。本项目每天都提交归档，天然避开了。 |
| 归档会被清 | `output.keep_days: 90` 默认保留 90 天，想永久保留改成 `0` |
| 有些站点抓不到正文 | 付费墙站点（Economist、Atlantic）已默认关闭；其它源抓不到时会退回 RSS 摘要，不会中断 |
| Anki 卡片怎么用 | 从仓库下载 `.apkg`，Anki 里「文件 → 导入」即可，会进入「外刊精读」牌组 |
| 首次运行很慢 | 第一次要装依赖 + 抓多个源，通常 2—5 分钟；之后正常 |

---

## 目录结构

```
外刊精读/
├── .github/workflows/daily-reading.yml   定时任务
├── config.yaml                           ★ 你日常只需要改这个
├── main.py                               主流程
├── requirements.txt
├── .env.example                          本地测试的环境变量模板
├── src/
│   ├── config.py     配置加载
│   ├── fetch.py      RSS 抓取与选文
│   ├── extract.py    正文抽取
│   ├── analyze.py    大模型精读
│   ├── render.py     渲染 Markdown / HTML
│   ├── mailer.py     邮件发送
│   └── anki.py       Anki 卡片生成
├── output/           每日精读归档（自动生成）
└── state/seen.json   去重记录（自动生成）
```

---

*每天一篇，读原文，也读世界。*
