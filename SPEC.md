# 飞书每日爆款文章推送系统 — 详细 SPEC

> 版本：v1.0 | 日期：2026-06-03 | 状态：待实现

---

## 一、系统概述

### 1.1 一句话定义

从公开免费数据源自动抓取微信公众号和头条的爆款文章，筛选出"低粉爆文"候选，通过飞书群机器人每日早晚推送精选卡片，同时将所有文章归档到飞书多维表格供月度复盘。

### 1.2 核心目标

| 目标 | 衡量标准 |
|------|----------|
| 自动发现爆文 | 每天从 2+ 数据源拉取 50-100 条爆文候选 |
| 低粉爆文筛选 | 通过阅读量阈值 + 排名区间近似筛选"中小号爆文" |
| 定时推送 | 早 9:00 + 晚 18:00，各推 10 条精选卡片 |
| 数据归档 | 每天全量文章写入飞书多维表格，按日期分表 |
| 零成本运行 | GitHub Actions + 免费数据源 + 飞书免费版 |

### 1.3 不做什么（v1 范围外）

- 不做文章正文抓取（反爬风险高）
- 不做 AI 摘要生成（v2 再考虑）
- 不做个性化分类订阅（v2 再考虑）
- 不做粉丝数精确判定（技术上不可能）

---

## 二、系统架构

```
┌──────────────────────────────────────────────────┐
│                  GitHub Actions                    │
│  ┌────────────────────────────────────────────┐   │
│  │              main.py (编排器)               │   │
│  │                                              │   │
│  │  ┌──────────────┐  ┌──────────────────┐    │   │
│  │  │ fetcher_      │  │ fetcher_          │    │   │
│  │  │ tophub.py     │  │ toutiao.py        │    │   │
│  │  │ (微信热文)    │  │ (头条热榜)        │    │   │
│  │  └──────┬───────┘  └──────┬───────────┘    │   │
│  │         │                  │                 │   │
│  │         └────────┬─────────┘                 │   │
│  │                  ▼                            │   │
│  │  ┌──────────────────────────────┐            │   │
│  │  │ filter_articles.py (筛选器)   │            │   │
│  │  │ • 热度过滤 • 排名区间 • 去重  │            │   │
│  │  │ • 综合评分 • 精选 Top 10     │            │   │
│  │  └──────────────┬───────────────┘            │   │
│  │                 │                             │   │
│  │     ┌───────────┴───────────┐                │   │
│  │     ▼                       ▼                 │   │
│  │  ┌──────────────┐  ┌──────────────────┐     │   │
│  │  │ feishu_       │  │ feishu_           │     │   │
│  │  │ sender.py     │  │ bitable.py        │     │   │
│  │  │ (卡片推送)    │  │ (多维表格归档)    │     │   │
│  │  └──────┬───────┘  └──────┬───────────┘     │   │
│  └─────────┼──────────────────┼─────────────────┘   │
└────────────┼──────────────────┼─────────────────────┘
             │                  │
             ▼                  ▼
     ┌──────────────┐  ┌──────────────────┐
     │  飞书群聊     │  │  飞书多维表格     │
     │  (卡片消息)   │  │  (数据归档)      │
     └──────────────┘  └──────────────────┘
```

---

## 三、数据源详细设计

### 3.1 源 A：tophub.today 微信公众号热文

| 属性 | 值 |
|------|-----|
| URL | `https://tophub.today/n/WnBe01o371` |
| 请求方式 | GET，带浏览器 User-Agent |
| 响应格式 | HTML 表格 |
| 数据量 | 约 30-50 条 |
| 更新频率 | 实时 |
| 失败策略 | 重试 1 次（间隔 60s），仍失败则跳过此源 |

**HTML 解析规则**（可能随网站改版变化）：

```
每行 <tr> 包含:
├── 排名 <td> : 数字（1-50）
├── 标题 <td> : <a> 标签，文本为标题，href 为原文链接
└── 热度 <td> : 文本，如 "2.3万"、"1567"

提取后字段:
{
  "rank": 15,
  "title": "为什么你的公众号阅读量越来越低",
  "url": "https://mp.weixin.qq.com/s/xxxx",
  "heat_score": 23000,       // 已清洗为整数
  "heat_display": "2.3万",   // 原始展示文本
  "source": "公众号",
  "fetched_at": "2026-06-03T09:00:00"
}
```

**热度值清洗规则**：
- `"2.3万"` → `23000`
- `"1.5 万"` → `15000`
- `"9876"` → `9876`
- `"10万+"` → `100000`
- 非数字 → `0`

### 3.2 源 B：今日头条热榜

| 属性 | 值 |
|------|-----|
| 主 URL | `https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc` |
| 备 URL | `https://api-hot.imsyy.top/toutiao` |
| 请求方式 | GET，主 URL 需带 Cookie `tt_webid` |
| 响应格式 | JSON |
| 数据量 | 约 50 条 |
| 失败策略 | 主 URL 失败 → fallback 到备 URL → 都失败则跳过 |

**主 URL 响应结构**：
```json
{
  "data": [
    {
      "Title": "某新闻标题",
      "ClusterId": "123456789",
      "HotValue": "915.6万",
      "Url": "https://www.toutiao.com/article/xxx/",
      "Label": "热"
    }
  ]
}
```

**备 URL (DailyHotApi) 响应结构**：
```json
{
  "data": [
    {
      "id": "123",
      "title": "某新闻标题",
      "hot": "915.6万",
      "url": "https://www.toutiao.com/article/xxx/"
    }
  ]
}
```

**提取后统一字段**：
```json
{
  "rank": 5,
  "title": "某新闻标题",
  "url": "https://www.toutiao.com/article/xxx/",
  "heat_score": 9156000,
  "heat_display": "915.6万",
  "source": "头条",
  "fetched_at": "2026-06-03T09:00:00"
}
```

---

## 四、筛选引擎设计

### 4.1 处理流程

```
step1: 加载 tophub 文章列表 + 头条文章列表
         │
step2: 热度初筛
         │  tophub: heat_score >= 2000 (可配置)
         │  toutiao: heat_score >= 5000 (标题单位不同)
         ▼
step3: 排名区间筛选
         │  只保留排名在 RANK_RANGE_START ~ RANK_RANGE_END 之间的文章
         │  默认 10~30（跳过前10名大号霸榜区）
         ▼
step4: 标题去重
         │  两两比较标题的 difflib.SequenceMatcher 相似度
         │  相似度 > 80% 视为重复，保留热度更高的那条
         │  跨源（tophub vs 头条）也做去重
         ▼
step5: 综合评分
         │  score = heat_score_normalized * 0.7 + rank_factor * 0.3
         │  rank_factor: 排名越靠后权重越高（鼓励发现"黑马"）
         ▼
step6: 排序取 Top N
         │  按 score 降序，取前 PICK_COUNT 条（默认 10）
         ▼
step7: 输出
          ├── picked_articles (精选10条) → 飞书卡片推送
          ├── all_articles (全部文章) → 飞书多维表格归档
          └── new_articles (当日新增，排除已推送过的) → 增量归档
```

### 4.2 去重逻辑详解

```python
def is_duplicate(title_a: str, title_b: str, threshold: float = 0.8) -> bool:
    """基于标题相似度判断是否为同一篇文章"""
    from difflib import SequenceMatcher
    return SequenceMatcher(None, title_a, title_b).ratio() > threshold

def deduplicate(articles: list) -> list:
    """
    1. 同一来源内去重（tohub 榜单内可能同一文章出现多次）
    2. 跨来源去重（同一篇文章可能同时在 tophub 和头条热榜）
    3. 保留热度更高的版本
    """
```

### 4.3 综合评分公式

```
normalized_heat = heat_score / max_heat_score_in_batch  (归一化到 0-1)
rank_factor = 1 - (rank - RANK_RANGE_START) / (RANK_RANGE_END - RANK_RANGE_START)
  → 排名越靠前(接近 RANK_RANGE_START) rank_factor 越高
  → 排名越靠后(接近 RANK_RANGE_END) rank_factor 越低
  → 但 rank_factor 权重只有 30%，所以热度仍然是主导因素

score = normalized_heat * 0.7 + rank_factor * 0.3
```

### 4.4 可配置参数

| 参数 | 默认值 | 环境变量 | 说明 |
|------|--------|----------|------|
| TOPHUB_HEAT_THRESHOLD | 2000 | `TOPHUB_HEAT_THRESHOLD` | tophub 最低热度 |
| TOUTIAO_HEAT_THRESHOLD | 5000 | `TOUTIAO_HEAT_THRESHOLD` | 头条最低热度 |
| RANK_RANGE_START | 10 | `RANK_RANGE_START` | 排名区间起点 |
| RANK_RANGE_END | 30 | `RANK_RANGE_END` | 排名区间终点 |
| PICK_COUNT | 10 | `PICK_COUNT` | 每次推送条数 |
| DEDUP_SIMILARITY_THRESHOLD | 0.8 | `DEDUP_THRESHOLD` | 去重相似度阈值 |

---

## 五、飞书卡片消息设计

### 5.1 消息类型

使用飞书自定义机器人 **interactive 卡片消息**。

### 5.2 早间卡片模板

```json
{
  "msg_type": "interactive",
  "card": {
    "config": { "wide_screen_mode": true },
    "header": {
      "template": "blue",
      "title": {
        "tag": "plain_text",
        "content": "☀️ 早间爆款文章精选 | 6月3日"
      }
    },
    "elements": [
      {
        "tag": "markdown",
        "content": "**1. [为什么你的公众号阅读量越来越低](https://mp.weixin.qq.com/s/xxx)**\n📎 公众号 · 热度 2.3万\n\n**2. [AI正在杀死内容创作者吗](https://www.toutiao.com/article/xxx)**\n📎 头条 · 热度 915.6万\n\n---\n*(共精选 10 条)*"
      },
      { "tag": "hr" },
      {
        "tag": "note",
        "elements": [
          { "tag": "plain_text", "content": "数据来源: tophub.today / 今日头条 | 推送时间: 2026-06-03 09:00 | 由 GitHub Actions 自动推送" }
        ]
      }
    ]
  }
}
```

### 5.3 晚间卡片模板

与早间相同，仅头部颜色改为 `turquoise`，标题改为"🌙 晚间爆款文章精选"。

### 5.4 异常通知模板

当所有数据源都失败时，发送简洁的异常通知：

```json
{
  "msg_type": "text",
  "content": {
    "text": "⚠️ 今日爆款文章推送异常：所有数据源均无法访问。请检查 GitHub Actions 日志。"
  }
}
```

---

## 六、飞书多维表格设计

### 6.1 表格结构

**表格名称**：`爆款文章归档`

**按日期分表**：每天自动创建子表，命名格式 `2026-06-03`

### 6.2 字段定义

| 字段名 | 类型 | ui_type | 必填 | 说明 |
|--------|------|---------|------|------|
| 序号 | 自动编号 | AutoNumber | 是 | 系统自动生成 |
| 标题 | 多行文本 | Text (1) | 是 | 文章标题，最长 10 万字符 |
| 来源 | 单选 | SingleSelect (3) | 是 | 公众号 / 头条 |
| 排名 | 数字 | Number (2) | 是 | 在源榜单中的排名 |
| 热度值 | 数字 | Number (2) | 是 | 清洗后的整数热度 |
| 热度展示 | 文本 | Text (1) | 否 | 原始展示文本，如"2.3万" |
| 原文链接 | 超链接 | Url (15) | 是 | 可点击跳转 |
| 推送日期 | 日期 | DateTime (5) | 是 | 归档日期 |
| 早晚班次 | 单选 | SingleSelect (3) | 否 | 早间 / 晚间 |
| 是否精选 | 复选框 | Checkbox (7) | 否 | 是否入选当日精选推送 |
| 精选评分 | 数字 | Number (2) | 否 | 综合评分（仅精选文章有值） |

### 6.3 API 操作流程

```
每天首次运行时:
1. POST /open-apis/bitable/v1/apps/{app_token}/tables
   → 创建日期子表（如果不存在）
   
2. POST /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields
   → 批量创建字段（新表第一次初始化）

3. POST /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create
   → 批量写入当日全量文章（上限 500 条，本项目约 80 条）
```

### 6.4 Bitable API 限流

| 限制 | 数值 | 本项目用量 | 是否触发 |
|------|------|------------|----------|
| 批量创建 | 单次 500 条 | 约 80 条/天 | 否 |
| 请求频率 | 触发码 9999140 | 低频调用 | 否 |
| 多行文本 | 单字段 100,000 字符 | 标题 ~50 字 | 否 |

---

## 七、飞书应用权限配置

### 7.1 需要的应用

**飞书企业自建应用**（Internal App），不需要审核上架。

### 7.2 需要的权限

| 权限代码 | 用途 | 说明 |
|----------|------|------|
| `bitable:app` | 操作多维表格 | 创建表、字段、记录 |
| `drive:drive` | 云空间文件操作 | 上传封面图附件时使用 |
| `im:message:send_by_bot` | 机器人发消息 | 如果不用 webhook 而用应用机器人 |

### 7.3 获取凭证

从飞书开发者后台获取：
- **App ID** (`cli_xxxxxxxx`)
- **App Secret**（一串随机字符）

SDK 用这两个自动换取 2 小时有效的 `tenant_access_token`。

---

## 八、配置文件设计

### 8.1 config.py 完整定义

```python
import os

# ── 飞书 Webhook（卡片推送） ──
FEISHU_WEBHOOK_URL = os.environ["FEISHU_WEBHOOK_URL"]
FEISHU_WEBHOOK_SECRET = os.environ.get("FEISHU_WEBHOOK_SECRET", "")

# ── 飞书应用（Bitable 归档） ──
FEISHU_APP_ID = os.environ["FEISHU_APP_ID"]
FEISHU_APP_SECRET = os.environ["FEISHU_APP_SECRET"]
FEISHU_BITABLE_APP_TOKEN = os.environ["FEISHU_BITABLE_APP_TOKEN"]

# ── 数据源 URL ──
TOPHUB_WEIXIN_URL = "https://tophub.today/n/Jb0vmloB1G"
TOUTIAO_API_URL = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"
DAILYHOT_API_URL = "https://api-hot.imsyy.top/toutiao"

# ── 筛选参数 ──
TOPHUB_HEAT_THRESHOLD = int(os.environ.get("TOPHUB_HEAT_THRESHOLD", "2000"))
TOUTIAO_HEAT_THRESHOLD = int(os.environ.get("TOUTIAO_HEAT_THRESHOLD", "5000"))
RANK_RANGE_START = int(os.environ.get("RANK_RANGE_START", "10"))
RANK_RANGE_END = int(os.environ.get("RANK_RANGE_END", "30"))
PICK_COUNT = int(os.environ.get("PICK_COUNT", "10"))
DEDUP_THRESHOLD = float(os.environ.get("DEDUP_THRESHOLD", "0.8"))

# ── 推送时段 ──
PUSH_SESSION = os.environ.get("PUSH_SESSION", "morning")  # morning | evening
```

### 8.2 .env.example（本地测试用）

```
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx
FEISHU_WEBHOOK_SECRET=your_webhook_secret
FEISHU_APP_ID=cli_xxxxxxxx
FEISHU_APP_SECRET=your_app_secret
FEISHU_BITABLE_APP_TOKEN=your_bitable_token
```

---

## 九、GitHub Actions 配置

### 9.1 Workflow 文件

```yaml
name: 每日爆款文章推送

on:
  schedule:
    - cron: '0 1 * * *'   # 北京时间 09:00
    - cron: '0 10 * * *'  # 北京时间 18:00
  workflow_dispatch:

jobs:
  push:
    runs-on: ubuntu-latest
    timeout-minutes: 5

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run (morning)
        if: github.event.schedule == '0 1 * * *'
        env:
          FEISHU_WEBHOOK_URL: ${{ secrets.FEISHU_WEBHOOK_URL }}
          FEISHU_WEBHOOK_SECRET: ${{ secrets.FEISHU_WEBHOOK_SECRET }}
          FEISHU_APP_ID: ${{ secrets.FEISHU_APP_ID }}
          FEISHU_APP_SECRET: ${{ secrets.FEISHU_APP_SECRET }}
          FEISHU_BITABLE_APP_TOKEN: ${{ secrets.FEISHU_BITABLE_APP_TOKEN }}
          PUSH_SESSION: morning
        run: python main.py

      - name: Run (evening)
        if: github.event.schedule == '0 10 * * *'
        env:
          FEISHU_WEBHOOK_URL: ${{ secrets.FEISHU_WEBHOOK_URL }}
          FEISHU_WEBHOOK_SECRET: ${{ secrets.FEISHU_WEBHOOK_SECRET }}
          FEISHU_APP_ID: ${{ secrets.FEISHU_APP_ID }}
          FEISHU_APP_SECRET: ${{ secrets.FEISHU_APP_SECRET }}
          FEISHU_BITABLE_APP_TOKEN: ${{ secrets.FEISHU_BITABLE_APP_TOKEN }}
          PUSH_SESSION: evening
        run: python main.py
```

### 9.2 Secrets 清单

| Secret 名称 | 必填 | 说明 |
|-------------|------|------|
| `FEISHU_WEBHOOK_URL` | 是 | 群机器人 Webhook 地址 |
| `FEISHU_WEBHOOK_SECRET` | 否 | Webhook 签名密钥 |
| `FEISHU_APP_ID` | 是 | 飞书应用 App ID |
| `FEISHU_APP_SECRET` | 是 | 飞书应用 App Secret |
| `FEISHU_BITABLE_APP_TOKEN` | 是 | 多维表格 App Token |

---

## 十、费用估算

| 项目 | 用量 | 免费额度 | 是否足够 |
|------|------|----------|----------|
| GitHub Actions | ~30 分钟/月 | 2000 分钟/月 | ✅ |
| tophub.today | ~60 请求/月 | 免费 | ✅ |
| toutiao API | ~60 请求/月 | 免费 | ✅ |
| DailyHotApi | 仅 fallback | 免费 | ✅ |
| 飞书 Webhook | ~60 条/月 | 100 条/分钟 | ✅ |
| 飞书 Bitable API | ~90 次写/月 | 免费 | ✅ |
| 飞书多维表格行数 | ~2400 行/月 | 免费版有限制 | ⚠️ 需关注 |

**总计：0 元。**

> ⚠️ 飞书免费版多维表格单表行数有上限（通常几千行）。如果归档量累积过大，需要定期清理旧数据或手动归档。

---

## 十一、用户操作清单

### 阶段 1：飞书准备（10 分钟）

- [ ] 1. 创建飞书群聊，命名为"爆款文章推送"
- [ ] 2. 添加自定义机器人，获取 Webhook URL
- [ ] 3. （可选）设置签名校验，保存密钥

### 阶段 2：飞书开放平台准备（15 分钟）

- [ ] 4. 打开 [飞书开发者后台](https://open.feishu.cn/app)
- [ ] 5. 创建「企业自建应用」，命名"爆款文章助手"
- [ ] 6. 添加权限：`bitable:app`、`drive:drive`
- [ ] 7. 发布应用（设置可见范围为自己）
- [ ] 8. 复制 App ID、App Secret

### 阶段 3：创建多维表格（5 分钟）

- [ ] 9. 在飞书云空间手动创建一个多维表格，命名"爆款文章归档"
- [ ] 10. 复制多维表格的 App Token（URL 中 `base/` 后面的部分）
- [ ] 11. 将该表关联到刚才创建的应用（协作权限）

### 阶段 4：GitHub 准备（10 分钟）

- [ ] 12. 创建 GitHub 仓库（Private 推荐）
- [ ] 13. 推送代码到仓库
- [ ] 14. 配置 5 个 GitHub Secrets
- [ ] 15. 手动触发一次 Actions 测试

### 阶段 5：验证（5 分钟）

- [ ] 16. 检查飞书群是否收到卡片消息
- [ ] 17. 检查多维表格是否有当日数据写入
- [ ] 18. 等待第二天早 9 点，确认定时推送正常

---

## 十二、项目文件清单

| 文件 | 行数估算 | 职责 |
|------|----------|------|
| `SPEC.md` | — | 本文档，系统规格说明书 |
| `main.py` | ~60 行 | 编排器：串联拉取、筛选、推送、归档 |
| `config.py` | ~30 行 | 配置项集中管理 + 环境变量读取 |
| `fetcher_tophub.py` | ~80 行 | tophub HTML 解析 + 数据清洗 |
| `fetcher_toutiao.py` | ~90 行 | 头条 JSON 获取 + fallback + 字段映射 |
| `filter_articles.py` | ~120 行 | 过滤、去重、评分、精选 |
| `feishu_sender.py` | ~100 行 | 卡片 JSON 拼装 + Webhook POST |
| `feishu_bitable.py` | ~150 行 | 飞书应用认证 + Bitable 表/字段/记录管理 |
| `requirements.txt` | ~5 行 | lark-oapi, requests, beautifulsoup4 |
| `.github/workflows/daily_push.yml` | ~50 行 | CI 定时任务 |
