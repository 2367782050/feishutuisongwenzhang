import base64
import hashlib
import hmac
import time
import requests
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))


def _gen_sign(timestamp: int, secret: str) -> str:
    """生成飞书 webhook 签名（HMAC-SHA256 + Base64）"""
    string_to_sign = f"{timestamp}\n{secret}"
    h = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256)
    return base64.b64encode(h.digest()).decode("utf-8")


def build_card(articles: list[dict], session: str) -> dict:
    """构建按赛道分组的卡片消息"""
    now = datetime.now(CST)
    date_str = now.strftime("%m月%d日")
    time_str = now.strftime("%H:%M")

    color = "blue"
    title = f"公众号爆款文章精选 | {date_str}"

    # 按赛道分组
    from collections import OrderedDict
    cats = OrderedDict()
    for art in articles:
        tags = art.get("quality_tags", [])
        cat = next((t for t in tags if t not in ("blocked", "低质信号", "优质信号", "其他")), "其他")
        cats.setdefault(cat, []).append(art)

    elements = []

    for cat, arts in cats.items():
        # 赛道标题
        emoji_map = {
            "科技·AI": "🤖", "情感": "💕", "健康养生": "🌿",
            "个人成长": "📈", "历史": "📜", "体制": "🏛️", "家居": "🏠",
        }
        emoji = emoji_map.get(cat, "📌")
        elements.append({
            "tag": "markdown",
            "content": f"**{emoji} {cat}**（{len(arts)}篇）"
        })

        # 文章列表（每赛道最多5篇，已由筛选器保证）
        for i, art in enumerate(arts, 1):
            title_text = art["title"]
            if len(title_text) > 45:
                title_text = title_text[:45] + "..."
            teaser = art.get("summary", "")
            teaser_line = f"  {teaser}" if teaser else ""
            elements.append({
                "tag": "markdown",
                "content": (
                    f"{i}. [{title_text}]({art['url']})\n"
                    f"  热度 {art['heat_display']}{teaser_line}"
                )
            })

        elements.append({"tag": "hr"})

    # 移除最后一个分割线
    if elements and elements[-1].get("tag") == "hr":
        elements.pop()

    # 底部统计
    total = len(articles)
    cat_count = len(cats)
    elements.append({
        "tag": "note",
        "elements": [{
            "tag": "plain_text",
            "content": (
                f"共 {total} 篇 · {cat_count} 个赛道 | "
                f"数据来源: tophub.today 微信24h热文榜 | "
                f"推送时间: {now.strftime('%Y-%m-%d')} {time_str}"
            ),
        }],
    })

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": color,
                "title": {"tag": "plain_text", "content": title},
            },
            "elements": elements,
        },
    }


def send_card(webhook_url: str, secret: str, articles: list[dict], session: str):
    """发送卡片消息到飞书群"""
    card = build_card(articles, session)

    payload = {"msg_type": "interactive", "card": card["card"]}

    if secret:
        timestamp = str(int(time.time()))
        payload["timestamp"] = timestamp
        payload["sign"] = _gen_sign(int(timestamp), secret)

    resp = requests.post(webhook_url, json=payload, timeout=15)
    data = resp.json()

    if data.get("code") != 0:
        raise RuntimeError(f"飞书 webhook 返回错误: {data}")

    return data


def send_error_notification(webhook_url: str, secret: str, message: str):
    """推送异常通知"""
    timestamp = int(time.time())
    sign = _gen_sign(timestamp, secret) if secret else ""

    payload = {
        "timestamp": str(timestamp),
        "sign": sign,
        "msg_type": "text",
        "content": {"text": f"⚠️ 爆款文章推送异常：{message}\n请检查 GitHub Actions 日志。"},
    }

    requests.post(webhook_url, json=payload, timeout=15)
