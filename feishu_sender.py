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
    """构建飞书 interactive 卡片消息 JSON"""
    now = datetime.now(CST)
    date_str = now.strftime("%m月%d日")
    time_str = now.strftime("%H:%M")

    if session == "morning":
        color = "blue"
        title = f"早间爆款文章精选 | {date_str}"
    else:
        color = "turquoise"
        title = f"晚间爆款文章精选 | {date_str}"

    lines = []
    for i, art in enumerate(articles, 1):
        title_text = art["title"]
        if len(title_text) > 50:
            title_text = title_text[:50] + "..."
        # 取第一个非 block/低质/优质 的分类标签
        tags = art.get("quality_tags", [])
        category = next((t for t in tags if t not in ("blocked", "低质信号", "优质信号")), "")
        cat_str = f" · {category}" if category else ""
        lines.append(
            f"**{i}. [{title_text}]({art['url']})**\n"
            f"{art['source']}{cat_str} · 热度 {art['heat_display']}\n"
        )

    body = "\n".join(lines)

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": color,
                "title": {"tag": "plain_text", "content": title},
            },
            "elements": [
                {"tag": "markdown", "content": body},
                {"tag": "hr"},
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": (
                                f"共精选 {len(articles)} 条 | "
                                f"数据来源: tophub.today / 今日头条 | "
                                f"推送时间: {now.strftime('%Y-%m-%d')} {time_str} | "
                                f"由 GitHub Actions 自动推送"
                            ),
                        }
                    ],
                },
            ],
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
