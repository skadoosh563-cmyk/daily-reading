# 外刊精读

每天早上自动给你一篇外刊精读：**导读 → 原文 → 逐段翻译 → 生词表 → 长难句拆解 → 理解题**，
邮件直达、微信可收，同时生成 Anki 卡片包，并把当天内容发布成一个**手机端学习页**
（生词按间隔重复算法复习）。

零服务器、零成本（公开仓库 Actions 免费），部署一次之后每天自动运行。

---

## 它每天做了什么

```
抓取 RSS  →  挑选一篇长度合适的  →  抓取正文全文  →  调用大模型精读
   ↓
生成 Markdown 归档 + HTML 邮件
   ↓
邮件推送 + 微信推送 + Anki 卡片(.apkg) + 提交回仓库
   ↓
导出结构化 JSON  →  GitHub Pages  →  手机网页版 / 微信小程序
```

去重记录存在 `state/seen.json`，同一篇文章不会被推第二次。

### 三样产出，各管什么

| 产出 | 位置 | 用途 |
| --- | --- | --- |
| 精读归档 | `output/年-月/` 下的 `.md` 和 `.html` | 完整精读，随时翻看 |
| Anki 卡片包 | `output/anki/外刊精读-日期.apkg` | 导入 Anki，电脑手机都能背 |
| 手机学习页 | `docs/`（发布到 GitHub Pages） | 打开链接就能读 + 背单词，带复习进度 |

---

## 部署：六步

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

### 4. 配微信推送（不想推微信可以跳过）

三个通道任选，配哪个开哪个，都在 `config.yaml` 的 `wechat` 段：

| 通道 | 怎么拿 | 适合 |
| --- | --- | --- |
| **Server 酱** | 到 [sct.ftqq.com](https://sct.ftqq.com) 微信扫码登录，复制 SendKey | 最省事，微信服务号直接收 |
| **企业微信群机器人** | 群设置 → 群机器人 → 添加 → 复制 Webhook 地址 | 想推给自己或同事的小群 |
| **自定义 Webhook** | 你自己的接口地址，会 POST 一段 JSON | 想转发到别处 |

拿到之后填进 Secrets（见下一步），再把 `config.yaml` 里对应通道改成 `true`
（`wechat.enabled` 是总开关，下面三个各自独立，只开你配了的那个）：

```yaml
wechat:
  enabled: true
  serverchan: true     # 用 Server 酱
  wecom: false         # 不用企业微信
  custom: false        # 不用自定义 webhook
```

推送内容是**摘要卡片**：中文标题 + 导读 + 生词表 + 理解题 + 原文链接——
不是全文，方便在微信里一眼扫完，想细读就点进原文或手机学习页。

### 5. 填 Secrets

仓库 → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`：

| 名称 | 说明 | 必填 |
| --- | --- | --- |
| `LLM_API_KEY` | 大模型 API Key | ✅ |
| `SMTP_SENDER` | 发件邮箱 | 可选 |
| `SMTP_PASSWORD` | SMTP 授权码 | 可选 |
| `SMTP_RECEIVER` | 收件邮箱，多个用逗号隔开 | 可选 |
| `SERVERCHAN_KEY` | Server 酱 SendKey | 可选 |
| `WECOM_WEBHOOK` | 企业微信群机器人 Webhook | 可选 |
| `CUSTOM_WEBHOOK` | 自定义推送地址 | 可选 |

没配的通道留空即可，脚本会自动跳过，不会报错。

### 6. 开权限并手动跑一次

- `Settings` → `Actions` → `General` → `Workflow permissions` 选 **Read and write permissions**
  （不然归档推不回去，任务会失败）
- `Actions` 标签页 → 左侧「每日外刊精读」→ `Run workflow`

看到邮件和仓库里多出 `output/` 目录，就成功了。之后每天北京时间早上 7 点自动跑。

---

## 手机端：两个选择

每天跑完，除了邮件和 Anki 卡片，还会导出一套结构化 JSON 到 `docs/`：
`docs/index.json`（文章列表）、`docs/vocab.json`（全部生词汇总）、`docs/daily/*.json`（每篇的详情）。
下面两条路都吃这套 JSON。

### 路线 A：网页版（推荐，零门槛）

不需要装任何东西，打开链接就能用。

1. 仓库 → `Settings` → `Pages` → `Source` 选 **GitHub Actions**
2. `Actions` 里跑一次工作流（或者等第二天自动跑）
3. 跑完访问 `https://你的用户名.github.io/外刊精读/`

页面顶部两个入口：**每日精读**（文章列表 + 详情，四个 tab：生词 / 翻译 / 长难句 / 理解题）
和**复习单词**（卡片式复习，三个评级：不认识 / 模糊 / 认识，用简化 SM-2 算法安排下次复习时间）。
学习进度存在手机浏览器本地（`localStorage`），不上传任何数据。

手机上「添加到主屏幕」就是个 App 图标。

### 路线 B：微信小程序（要装微信开发者工具）

小程序个人主体**不能做资讯类内容**，所以这里的定位是**背单词工具**：
只读 `vocab.json` 做复习，不展示文章全文，避免审核问题。

1. 下载 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)
2. 「导入项目」→ 目录选 `miniprogram/`，AppID 先用「测试号」即可
3. 改 `miniprogram/utils/config.js` 里的 `BASE`，填成你上面那个 Pages 地址，保存即可预览

想真机用，需要自己注册一个小程序 AppID（个人可注册，免费）后替换 `project.config.json` 里的 `appid`。

---

## 本地测试

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # 填 LLM_API_KEY 和邮箱授权码

python main.py --selftest        # 自检：不联网不调模型，验证渲染链路
python main.py --no-email        # 真跑一次但不发邮件
python main.py --url <文章链接>   # 指定一篇文章调试
python main.py --dump 原文.json   # 只抓原文存成 JSON，不调模型（先看看抓到什么）
```

### 样例文件

`samples/glp-1.json` 是一份**完整跑通的样例**（MIT Technology Review 的一篇报道 +
对应的精读结果）。想看成品长什么样，不用配任何 Key，直接：

```bash
python main.py --from-json samples/glp-1.json --no-email
```

生成的 Markdown、HTML 邮件和 Anki 卡片包会出现在 `output/` 里。
`output/2026-10/` 下已经放了一份渲染好的结果，可以直接打开看。

这个 JSON 也是**调试用的工作文件**：先 `--dump` 拿到原文，手工补上 `analysis`
字段，再用 `--from-json` 渲染——不花 API 额度就能反复调版式。

---

## 日常调整

**换素材源**：编辑 `config.yaml` 的 `sources`，加 `name` / `url` 两行即可；
不想要某个源，加 `enabled: false`。

**控制难度和长度**：`selection.min_words` / `max_words` 控制文章长度，
`study.level` 控制讲解深浅（A2 / B1 / B2 / C1）。

**每天多读几篇**：`selection.count: 2`。

**不想收邮件只要归档**：`email.enabled: false`。

**不想推微信**：`wechat.enabled: false`（只想关某一个通道，改它下面的 `serverchan` / `wecom` / `custom`）。
没配 Key 的通道会被自动跳过，所以三个都留 `true` 也不会报错。

**关掉 Anki 卡片**：`output.anki: false`。

**关掉手机端导出**：`app.enabled: false`。手机端历史保留多少天看 `app.keep_days`，
首页列几条看 `app.index_limit`。

---

## 会用到的坑（提前告诉你）

| 坑 | 说明 |
| --- | --- |
| cron 是 UTC | 想北京时间 7 点跑，写 `0 23 * * *`（前一天 UTC 23 点） |
| 60 天不活动会停 | 公开仓库长期无提交，定时任务会被 GitHub 自动禁用。本项目每天都提交归档，天然避开了。 |
| 归档会被清 | `output.keep_days: 90` 默认保留 90 天，想永久保留改成 `0` |
| 有些站点抓不到正文 | 付费墙站点（Economist、Atlantic）已默认关闭；其它源抓不到时会退回 RSS 摘要，不会中断 |
| 已自动过滤的内容 | 滚动直播（live blog）、图集、视频、播客、测验；以及 NPR 那类**广播转写稿**（满屏 SOUNDBITE / BYLINE，句子破碎，不适合精读） |
| 选文为什么先多抓几篇 | 正文长度要抓下来才知道，所以先取一批缓冲再筛。同源上限在缓冲阶段放宽到 3 篇，正式取文仍是 1 篇 |
| Anki 卡片怎么用 | 从仓库下载 `.apkg`，Anki 里「文件 → 导入」即可，会进入「外刊精读」牌组 |
| 首次运行很慢 | 第一次要装依赖 + 抓多个源，通常 2—5 分钟；之后正常 |
| Pages 打开是 404 | 第一次要去 `Settings → Pages` 把 Source 选成 **GitHub Actions**，并且等工作流**跑完**，才会第一次有内容。没配也不影响精读和推送——发布那一步会自动跳过 |
| 网页版数据没更新 | 手机浏览器缓存了 `index.json`。下拉刷新一次，或者换个无痕窗口看看 |
| 复习进度不同步 | 进度只存在手机本地（网页版 `localStorage`、小程序 `wx.storage`），换设备不跟着走，也不上传服务器 |
| 微信没收到推送 | 先确认对应 Key 已填进 Secrets 且 `config.yaml` 里那个通道是 `true`；Server 酱有每日条数上限，企业微信机器人被移出群会失效 |
| 小程序审核 | 个人主体不能做资讯/出版类内容。本项目小程序定位是**背单词工具**，只读生词数据、不展示文章全文，就是为了绕开这条 |

---

## 目录结构

```
外刊精读/
├── .github/workflows/daily-reading.yml   定时任务（含 Pages 发布）
├── config.yaml                           ★ 你日常只需要改这个
├── main.py                               主流程
├── requirements.txt
├── .env.example                          本地测试的环境变量模板
├── src/
│   ├── config.py      配置加载
│   ├── fetch.py       RSS 抓取、内容过滤与选文
│   ├── extract.py     正文抽取（含尾部导航清洗）
│   ├── analyze.py     大模型精读
│   ├── render.py      渲染 Markdown / HTML
│   ├── mailer.py      邮件发送
│   ├── wechat.py      微信推送（Server酱 / 企业微信 / 自定义）
│   ├── export_app.py  导出前端用的结构化 JSON
│   └── anki.py        Anki 卡片生成
├── docs/                 手机端静态页（自动生成，Pages 从这里发布）
│   ├── index.html        网页版（列表 / 复习 / 详情，零依赖）
│   ├── index.json        文章列表
│   ├── vocab.json        生词汇总（复习用）
│   └── daily/*.json      每篇详情
├── miniprogram/          微信小程序（背单词工具，需开发者工具导入）
├── samples/glp-1.json    可直接跑的完整样例（含精读结果）
├── output/           每日精读归档 + Anki 卡片（自动生成）
└── state/seen.json   去重记录（自动生成）
```

### 本地预览网页版

`docs/index.html` 是纯静态页，但它要用 `fetch` 读同目录的 JSON，
所以不能直接双击打开（`file://` 会被浏览器拦），起个本地服务即可：

```bash
python -m http.server 8777 --directory docs
# 然后浏览器打开 http://127.0.0.1:8777/
# 复习页：http://127.0.0.1:8777/#review
```

---

*每天一篇，读原文，也读世界。*
