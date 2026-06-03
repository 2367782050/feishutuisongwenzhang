import re

MAX_LEN = 80


def generate_teaser(article: dict) -> str:
    """
    基于标题和元数据生成一句话亮点，替代原文摘要。
    不抓原文（微信/头条都有反爬），但能帮用户判断是否值得点。
    """
    title = article.get("title", "")
    source = article.get("source", "")
    heat = article.get("heat_display", "")
    tags = article.get("quality_tags", [])
    score = article.get("score", 0)

    # 分类标签
    category = next((t for t in tags if t not in ("blocked", "低质信号", "优质信号")), "")

    # 热度描述
    heat_num = article.get("heat_score", 0)
    if heat_num >= 100000:
        heat_desc = "🔥 爆款"
    elif heat_num >= 50000:
        heat_desc = "热门"
    elif heat_num >= 10000:
        heat_desc = "上升中"
    else:
        heat_desc = "新晋"

    # 质量评价
    quality = article.get("quality_score", 0)
    if quality >= 2:
        quality_desc = "深度内容"
    elif quality >= 1:
        quality_desc = "值得一读"
    elif quality >= 0:
        quality_desc = ""
    else:
        quality_desc = ""

    # 拼装
    parts = [p for p in [heat_desc, category, quality_desc] if p]
    tagline = " · ".join(parts) if parts else ""

    # 截断标题
    short_title = title
    if len(short_title) > MAX_LEN:
        short_title = short_title[:MAX_LEN].rsplit(" ", 1)[0] + "..."

    return tagline


def batch_generate_teasers(articles: list[dict]):
    """为文章列表批量生成摘要"""
    for art in articles:
        art["summary"] = generate_teaser(art)

