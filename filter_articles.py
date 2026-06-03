from difflib import SequenceMatcher
from config import (
    RANK_RANGE_START,
    RANK_RANGE_END,
    PICK_COUNT,
    DEDUP_THRESHOLD,
)
from quality_filter import score_quality

# 各来源的最低热度阈值
HEAT_THRESHOLD = {
    "公众号": 2000,
    "头条": 5000,
    "知乎": 7000,
    "36氪": 7000,
    "微博": 5000,
}


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


def _normalize_and_score(articles: list[dict]) -> list[dict]:
    """综合评分：热度(40%) + 排名因子(20%) + 质量评分(40%)"""
    span = RANK_RANGE_END - RANK_RANGE_START or 1

    for art in articles:
        rank_factor = 1 - (art["rank"] - RANK_RANGE_START) / span
        art["_rank_factor"] = max(0, rank_factor)

    # 按来源独立归一化热度
    sources = {}
    for art in articles:
        sources.setdefault(art["source"], []).append(art)

    for src, arts in sources.items():
        max_heat = max(a["heat_score"] for a in arts) or 1
        for art in arts:
            art["_normalized_heat"] = art["heat_score"] / max_heat

    # 质量评分归一化（-3 到 +6 范围映射到 0-1）
    for art in articles:
        raw_q = art.get("quality_score", 0)
        art["_normalized_quality"] = max(0, min(1, (raw_q + 3) / 9))

    # 综合评分
    for art in articles:
        art["score"] = round(
            art["_normalized_heat"] * 0.4
            + art["_rank_factor"] * 0.2
            + art["_normalized_quality"] * 0.4,
            4,
        )
        del art["_normalized_heat"]
        del art["_rank_factor"]
        del art["_normalized_quality"]

    return articles


def filter_and_pick(tophub_articles: list[dict], toutiao_articles: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    筛选并精选文章。三步：硬过滤 → 综合评分 → 精选
    返回 (精选列表, 全量归档列表)
    """
    def _filter(art):
        threshold = HEAT_THRESHOLD.get(art["source"], 2000)
        return (
            art["heat_score"] >= threshold
            and RANK_RANGE_START <= art["rank"] <= RANK_RANGE_END
        )

    # 热度 + 排名区间过滤
    tophub_filtered = [a for a in tophub_articles if _filter(a)]
    toutiao_filtered = [a for a in toutiao_articles if _filter(a)]

    # 质量评估 + 硬过滤
    for art in tophub_filtered + toutiao_filtered:
        q = score_quality(art["title"])
        art["quality_score"] = q["score"]
        art["quality_tags"] = q["tags"]
        art["blocked"] = q["blocked"]

    # 移除被硬过滤的文章
    tophub_filtered = [a for a in tophub_filtered if not a["blocked"]]
    toutiao_filtered = [a for a in toutiao_filtered if not a["blocked"]]

    all_candidates = _deduplicate(tophub_filtered + toutiao_filtered)

    if not all_candidates:
        return [], []

    all_candidates = _normalize_and_score(all_candidates)
    all_candidates.sort(key=lambda a: a["score"], reverse=True)

    # 精选：每源最多 PICK_COUNT//3 条，保证多样性
    max_per_source = max(2, PICK_COUNT // 3)
    source_counts = {}
    picked = []
    for art in all_candidates:
        src = art["source"]
        count = source_counts.get(src, 0)
        if count < max_per_source:
            picked.append(art)
            source_counts[src] = count + 1
        if len(picked) >= PICK_COUNT:
            break

    # 如果不够 PICK_COUNT，不限来源补足
    if len(picked) < PICK_COUNT:
        for art in all_candidates:
            if art not in picked:
                picked.append(art)
            if len(picked) >= PICK_COUNT:
                break

    for art in picked:
        art["is_picked"] = True
    for art in all_candidates:
        if "is_picked" not in art:
            art["is_picked"] = False

    return picked, all_candidates
