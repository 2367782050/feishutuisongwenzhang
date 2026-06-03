from difflib import SequenceMatcher
from classifier import classify_articles
from quality_filter import score_quality

TARGET_CATEGORIES = ["科技·AI", "情感", "健康养生", "个人成长", "历史", "体制", "家居"]
MAX_PER_CATEGORY = 5
HOT_RESCUE_THRESHOLD = 50000  # "其他"分类中热度超过此值也推送


def _title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _deduplicate(articles: list[dict]) -> list[dict]:
    kept = []
    for art in articles:
        dup = False
        for existing in kept:
            if _title_similarity(art["title"], existing["title"]) > 0.8:
                dup = True
                if art["heat_score"] > existing["heat_score"]:
                    existing.update(art)
                break
        if not dup:
            kept.append(art)
    return kept


def _get_category(art: dict) -> str:
    tags = art.get("quality_tags", [])
    for tag in tags:
        if tag in TARGET_CATEGORIES:
            return tag
    return "其他"


def _cross_day_dedup(articles: list[dict], recent_titles: list[str]) -> list[dict]:
    """跨天去重：与最近文章标题对比，相似则跳过"""
    if not recent_titles:
        return articles
    kept = []
    for art in articles:
        dup = False
        for rt in recent_titles:
            if _title_similarity(art["title"], rt) > 0.75:
                dup = True
                break
        if not dup:
            kept.append(art)
    return kept


def filter_and_pick(articles: list[dict], _unused: list[dict],
                    recent_titles: list[str] | None = None,
                    account_frequency: dict[str, int] | None = None) -> tuple[list[dict], list[dict]]:
    """
    筛选流程：质量过滤 → AI分类 → 去重 → 新颖度评分 → 赛道精选 + 热门兜底
    返回 (精选列表, 全量归档列表)
    """
    if recent_titles is None:
        recent_titles = []
    if account_frequency is None:
        account_frequency = {}

    # 1. 质量评估 + 硬过滤
    for art in articles:
        q = score_quality(art["title"])
        art["quality_score"] = q["score"]
        art["blocked"] = q["blocked"]

    candidates = [a for a in articles if not a["blocked"]]

    # 2. AI 分类（替换关键词分类）
    classify_articles(candidates)

    # 3. 同天去重 + 跨天去重
    candidates = _deduplicate(candidates)
    candidates = _cross_day_dedup(candidates, recent_titles)

    # 4. 新颖度评分：低频账号 = 可能的低粉爆文
    for art in candidates:
        biz = art.get("account_id", "")
        freq = account_frequency.get(biz, 0) if biz else -1
        art["account_freq"] = freq

        if freq == 0:
            art["novelty"] = "🆕 新面孔"
            art["novelty_score"] = 2.0
        elif freq <= 2:
            art["novelty"] = "🌟 偶尔出现"
            art["novelty_score"] = 1.0
        else:
            art["novelty"] = ""
            art["novelty_score"] = 0

    # 5. 综合评分
    for art in candidates:
        art["score"] = round(
            art.get("quality_score", 0)
            + art["heat_score"] / 10000
            + art["novelty_score"],
            4,
        )

    # 6. 按赛道分组
    categories = {}
    for art in candidates:
        cat = _get_category(art)
        categories.setdefault(cat, []).append(art)

    for cat in categories:
        categories[cat].sort(key=lambda a: a["score"], reverse=True)

    # 7. 赛道精选（最多 5 篇/赛道）
    picked = []
    for cat in TARGET_CATEGORIES:
        pool = categories.get(cat, [])
        picked.extend(pool[:MAX_PER_CATEGORY])

    # 8. 热门兜底："其他"分类中热度 > 阈值的前 5 名也推
    other_pool = categories.get("其他", [])
    hot_others = [a for a in other_pool if a["heat_score"] >= HOT_RESCUE_THRESHOLD]
    hot_others.sort(key=lambda a: a["heat_score"], reverse=True)
    picked.extend(hot_others[:5])

    # 标记精选
    picked_ids = {id(a) for a in picked}
    for art in candidates:
        art["is_picked"] = id(art) in picked_ids

    return picked, candidates
