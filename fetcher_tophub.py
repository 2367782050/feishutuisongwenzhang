import re
import requests
from bs4 import BeautifulSoup
from config import TOPHUB_WEIXIN_URL

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}


def _clean_heat(text: str) -> tuple[int, str]:
    """将热度文本清洗为整数和展示文本。如 '2.3万' → (23000, '2.3万')"""
    text = text.strip()
    display = text
    text = text.replace(",", "").replace("，", "")

    if "万" in text:
        num = float(text.replace("万", "").strip())
        return int(num * 10000), display

    try:
        return int(float(text)), display
    except ValueError:
        return 0, display


def fetch_tophub_weixin() -> list[dict]:
    """从 tophub.today 抓取微信公众号热文列表"""
    resp = requests.get(TOPHUB_WEIXIN_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    resp.encoding = "utf-8"

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []

    for row in soup.select("table.table tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        a_tag = cells[1].find("a")
        if not a_tag:
            continue

        title = a_tag.get_text(strip=True)
        url = a_tag.get("href", "")
        rank_text = cells[0].get_text(strip=True).rstrip(".")
        heat_text = cells[2].get_text(strip=True)

        try:
            rank = int(rank_text)
        except ValueError:
            continue

        heat_score, heat_display = _clean_heat(heat_text)

        articles.append({
            "rank": rank,
            "title": title,
            "url": url,
            "heat_score": heat_score,
            "heat_display": heat_display,
            "source": "公众号",
        })

    return articles
