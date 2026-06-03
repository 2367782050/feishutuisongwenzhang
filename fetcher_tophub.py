import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}

# 节点配置: (node_id, source_name, layout)
# layout: "standard" = td[1]标题 + td[2]热度, "no_heat" = td[2]标题 无热度列
NODES = {
    "公众号": ("WnBe01o371", "standard"),
    "知乎": ("mproPpoq6O", "no_heat"),
    "36氪": ("Q1Vd5Ko85R", "no_heat"),
    "微博": ("KqndgxeLl9", "standard"),
}


def _clean_heat(text: str) -> tuple[int, str]:
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


def fetch_tophub_node(node_id: str, source_name: str, layout: str = "standard") -> list[dict]:
    """从 tophub.today 指定节点抓取热榜"""
    url = f"https://tophub.today/n/{node_id}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    resp.encoding = "utf-8"

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []

    for row in soup.select("table.table tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        # 提取排名
        rank_text = cells[0].get_text(strip=True).rstrip(".")
        try:
            rank = int(rank_text)
        except ValueError:
            continue

        if layout == "no_heat":
            # 无热度列：td[2] 是标题链接
            a_tag = cells[2].find("a") if len(cells) > 2 else None
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            url = a_tag.get("href", "")
            heat_score = 10000 - rank * 100  # 用排名模拟热度
            heat_display = f"热榜第{rank}"
        else:
            # 标准布局：td[1] 标题, td[2] 热度
            a_tag = cells[1].find("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            url = a_tag.get("href", "")
            heat_text = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            heat_score, heat_display = _clean_heat(heat_text)

        articles.append({
            "rank": rank,
            "title": title,
            "url": url,
            "heat_score": heat_score,
            "heat_display": heat_display,
            "source": source_name,
        })

    return articles


def fetch_tophub_weixin() -> list[dict]:
    nid, layout = NODES["公众号"]
    return fetch_tophub_node(nid, "公众号", layout)


def fetch_zhihu() -> list[dict]:
    nid, layout = NODES["知乎"]
    return fetch_tophub_node(nid, "知乎", layout)


def fetch_36kr() -> list[dict]:
    nid, layout = NODES["36氪"]
    return fetch_tophub_node(nid, "36氪", layout)


def fetch_weibo() -> list[dict]:
    nid, layout = NODES["微博"]
    return fetch_tophub_node(nid, "微博", layout)
