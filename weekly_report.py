"""每周复盘报告：汇总一周数据 + DeepSeek 趋势分析"""
import json
import os
import re
import requests
from datetime import datetime, timezone, timedelta
from collections import Counter

CST = timezone(timedelta(hours=8))
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
BASE_URL = "https://open.feishu.cn/open-apis"

TARGET_CATEGORIES = ["科技·AI", "情感", "健康养生", "个人成长", "历史", "体制", "家居"]
CAT_EMOJI = {
    "科技·AI": "🤖", "情感": "💕", "健康养生": "🌿",
    "个人成长": "📈", "历史": "📜", "体制": "🏛️", "家居": "🏠", "其他": "📌",
}


def _get_token(app_id: str, app_secret: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=15,
    )
    return resp.json()["tenant_access_token"]


def _fetch_week_data(app_id: str, app_secret: str, app_token: str) -> dict:
    """从 Bitable 拉取过去 7 天的全量数据"""
    token = _get_token(app_id, app_secret)

    # 列出所有表
    resp = requests.get(
        f"{BASE_URL}/bitable/v1/apps/{app_token}/tables",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    tables = resp.json().get("data", {}).get("items", [])

    today = datetime.now(CST).date()
    recent_dates = {(today - timedelta(days=d)).strftime("%Y-%m-%d") for d in range(7)}

    all_records = []
    for tbl in tables:
        tbl_name = tbl.get("name", "")
        if tbl_name not in recent_dates:
            continue
        tbl_id = tbl["table_id"]
        resp = requests.get(
            f"{BASE_URL}/bitable/v1/apps/{app_token}/tables/{tbl_id}/records",
            headers={"Authorization": f"Bearer {token}"},
            params={"page_size": 100},
            timeout=15,
        )
        data = resp.json()
        if data.get("code") != 0:
            continue
        for item in data.get("data", {}).get("items", []):
            all_records.append(item.get("fields", {}))

    return _aggregate(all_records)


def _aggregate(records: list[dict]) -> dict:
    """聚合统计数据"""
    stats = {
        "total": len(records),
        "categories": Counter(),
        "picked": 0,
        "new_accounts": 0,
        "top_articles": [],
        "hot_accounts": Counter(),
        "daily_counts": Counter(),
    }

    for r in records:
        cat = str(r.get("分类", "其他"))
        stats["categories"][cat] += 1

        if r.get("是否精选"):
            stats["picked"] += 1

        novelty = str(r.get("亮点标签", ""))
        if "新面孔" in novelty:
            stats["new_accounts"] += 1

        aid = str(r.get("账号ID", ""))
        if aid:
            stats["hot_accounts"][aid[:20]] += 1

    # Top 文章（按精选评分）
    def _score(r):
        try:
            return float(r.get("精选评分", 0))
        except (ValueError, TypeError):
            return 0.0

    scored = [r for r in records if _score(r) > 0]
    scored.sort(key=_score, reverse=True)
    stats["top_articles"] = scored[:10]

    return stats


def _generate_ai_summary(stats: dict) -> str:
    """用 DeepSeek 生成趋势分析"""
    if not DEEPSEEK_API_KEY:
        return ""

    # 准备数据
    cat_summary = "、".join(
        f"{cat}{stats['categories'].get(cat, 0)}篇"
        for cat in TARGET_CATEGORIES if stats["categories"].get(cat, 0) > 0
    )
    top_titles = "\n".join(
        f"- {a.get('标题', '')}" for a in stats["top_articles"][:5]
    )

    prompt = (
        f"你是一个公众号爆文分析师。以下是过去一周的爆文数据：\n\n"
        f"总文章数: {stats['total']}\n"
        f"赛道分布: {cat_summary}\n"
        f"新面孔账号: {stats['new_accounts']} 个\n"
        f"最热文章:\n{top_titles}\n\n"
        f"请写两段分析（每段≤80字）:\n"
        f"1. 本周最值得关注的变化或趋势\n"
        f"2. 对公众号创作者的选题建议\n"
        f"直接输出内容，不要编号，不要标记。"
    )

    try:
        resp = requests.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5,
                "max_tokens": 400,
            },
            timeout=30,
        )
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return ""


def build_weekly_card(stats: dict, ai_summary: str) -> dict:
    """构建每周复盘卡片"""
    now = datetime.now(CST)
    week_start = (now.date() - timedelta(days=7)).strftime("%m/%d")
    week_end = now.date().strftime("%m/%d")

    elements = []

    # 总体概览
    elements.append({
        "tag": "markdown",
        "content": (
            f"**📊 {week_start} - {week_end}**  "
            f"共推送 {stats['total']} 篇文章，"
            f"新面孔 {stats['new_accounts']} 个"
        ),
    })

    # 赛道活跃度
    cat_lines = []
    for cat in TARGET_CATEGORIES:
        count = stats["categories"].get(cat, 0)
        if count > 0:
            bar = "█" * min(count, 15)
            emoji = CAT_EMOJI.get(cat, "")
            cat_lines.append(f"{emoji} **{cat}** {bar} {count}篇")
    if cat_lines:
        elements.append({"tag": "markdown", "content": "**🏆 赛道活跃度**\n" + "\n".join(cat_lines)})
        elements.append({"tag": "hr"})

    # Top 5 文章
    top_arts = stats["top_articles"][:5]
    if top_arts:
        top_lines = ["**🔥 本周最值得关注的 5 篇**"]
        for i, a in enumerate(top_arts, 1):
            title = str(a.get("标题", ""))
            cat = str(a.get("分类", ""))
            novelty = str(a.get("亮点标签", ""))
            link_raw = a.get("原文链接", "")
            if isinstance(link_raw, dict):
                link = link_raw.get("link", "")
            else:
                link = str(link_raw)
            is_new = "🆕 " if "新面孔" in novelty else ""
            top_lines.append(f"{i}. {is_new}[{title[:40]}]({link})  _{cat}_")
        elements.append({"tag": "markdown", "content": "\n".join(top_lines)})
        elements.append({"tag": "hr"})

    # AI 趋势分析
    if ai_summary:
        elements.append({"tag": "markdown", "content": f"**📈 趋势观察**\n{ai_summary}"})
        elements.append({"tag": "hr"})

    # 底部
    elements.append({
        "tag": "note",
        "elements": [{
            "tag": "plain_text",
            "content": f"数据来源: 公众号微信24h热文榜 | 每周一自动生成 | {now.strftime('%Y-%m-%d')}",
        }],
    })

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "purple",
                "title": {"tag": "plain_text", "content": f"📊 公众号爆文周报 | {week_start} - {week_end}"},
            },
            "elements": elements,
        },
    }


def send_weekly_report(app_id: str, app_secret: str, app_token: str,
                       webhook_url: str, webhook_secret: str = ""):
    """生成并发送每周复盘报告"""
    print("生成每周复盘报告...")
    stats = _fetch_week_data(app_id, app_secret, app_token)
    print(f"  拉取: {stats['total']} 条记录, {stats['picked']} 条精选, {stats['new_accounts']} 新面孔")

    if stats["total"] == 0:
        print("  ⚠️ 本周无数据，跳过")
        return

    ai_summary = _generate_ai_summary(stats)
    print(f"  AI 分析: {'OK' if ai_summary else '跳过'}")

    card = build_weekly_card(stats, ai_summary)

    payload = {"msg_type": "interactive", "card": card["card"]}
    if webhook_secret:
        import hmac, hashlib, base64
        ts = str(int(datetime.now(CST).timestamp()))
        sign_str = f"{ts}\n{webhook_secret}"
        h = hmac.new(webhook_secret.encode(), sign_str.encode(), hashlib.sha256)
        payload["timestamp"] = ts
        payload["sign"] = base64.b64encode(h.digest()).decode()

    resp = requests.post(webhook_url, json=payload, timeout=15)
    data = resp.json()
    if data.get("code") != 0:
        print(f"  ❌ 发送失败: {data}")
    else:
        print("  ✅ 周报已发送")
