import re
import requests
from config import TOUTIAO_API_URL, DAILYHOT_API_URL

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.toutiao.com/",
}


def _clean_heat(text: str) -> tuple[int, str]:
    text = str(text).strip()
    display = text
    text = text.replace(",", "").replace("，", "")

    if "万" in text:
        num = float(text.replace("万", "").strip())
        return int(num * 10000), display

    try:
        return int(float(text)), display
    except ValueError:
        return 0, display


def _parse_toutiao_response(data: dict) -> list[dict]:
    """解析头条官方 API 响应"""
    articles = []
    items = data.get("data", [])
    for i, item in enumerate(items, 1):
        title = item.get("Title", "")
        url = item.get("Url", "")
        if not title:
            continue
        heat_score, heat_display = _clean_heat(item.get("HotValue", "0"))
        articles.append({
            "rank": i,
            "title": title,
            "url": url,
            "heat_score": heat_score,
            "heat_display": heat_display,
            "source": "头条",
        })
    return articles


def _parse_dailyhot_response(data: dict) -> list[dict]:
    """解析 DailyHotApi 响应"""
    articles = []
    items = data.get("data", [])
    for i, item in enumerate(items, 1):
        title = item.get("title", "")
        url = item.get("url", "")
        if not title:
            continue
        heat_score, heat_display = _clean_heat(item.get("hot", "0"))
        articles.append({
            "rank": i,
            "title": title,
            "url": url,
            "heat_score": heat_score,
            "heat_display": heat_display,
            "source": "头条",
        })
    return articles


def fetch_toutiao() -> list[dict]:
    """获取头条热榜，官方 API 失败则 fallback 到 DailyHotApi"""
    # 尝试官方 API
    try:
        resp = requests.get(TOUTIAO_API_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return _parse_toutiao_response(resp.json())
    except Exception:
        pass

    # fallback 到 DailyHotApi
    try:
        resp = requests.get(DAILYHOT_API_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return _parse_dailyhot_response(resp.json())
    except Exception:
        return []
