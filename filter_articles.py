from difflib import SequenceMatcher
from config import PICK_COUNT, DEDUP_THRESHOLD
from quality_filter import score_quality

# 目标赛道（按优先级排列）
TARGET_CATEGORIES = [
    "科技·AI", "情感", "健康养生", "个人成长",
    "历史", "体制", "家居",
]

MAX_PER_CATEGORY = 5


def _title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _deduplicate(articles: list[dict]) -> list[dict]:
    kept = []
    for art in articles:
        dup = False
        for i, existing in enumerate(kept):
            if _title_similarity(art["title"], existing["title"]) > DEDUP_THRESHOLD:
                dup = True
                if art["heat_score"] > existing["heat_score"]:
                    kept[i] = art
                break
        if not dup:
            kept.append(art)
    return kept


def _get_category(art: dict) -> str:
    """从 quality_tags 中提取分类标签"""
    tags = art.get("quality_tags", [])
    for tag in tags:
        if tag in TARGET_CATEGORIES:
            return tag
    return "其他"


def filter_and_pick(tophub_articles: list[dict], toutiao_articles: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    按赛道筛选公众号文章。
    每赛道最多 5 篇，其他分类的文章不入精选但保留归档。
    返回 (精选列表, 全量归档列表)
    """
    all_raw = tophub_articles + toutiao_articles

    # 质量评估 + 硬过滤
    for art in all_raw:
        q = score_quality(art["title"])
        art["quality_score"] = q["score"]
        art["quality_tags"] = q["tags"]
        art["blocked"] = q["blocked"]

    # 移除被硬过滤的文章
    candidates = [a for a in all_raw if not a["blocked"]]

    # 去重
    candidates = _deduplicate(candidates)

    # 计算综合评分（不用多源归一化，公众号只有一个源）
    for art in candidates:
        art["score"] = round(art.get("quality_score", 0) + art["heat_score"] / 10000, 4)

    # 按赛道分组
    categories = {}
    for art in candidates:
        cat = _get_category(art)
        categories.setdefault(cat, []).append(art)

    # 每赛道按评分排序
    for cat in categories:
        categories[cat].sort(key=lambda a: a["score"], reverse=True)

    # 精选：目标赛道各取最多 MAX_PER_CATEGORY 篇
    picked = []
    for cat in TARGET_CATEGORIES:
        pool = categories.get(cat, [])
        picked.extend(pool[:MAX_PER_CATEGORY])

    # 标记精选
    picked_ids = {id(a) for a in picked}
    for art in candidates:
        art["is_picked"] = id(art) in picked_ids

    return picked, candidates
