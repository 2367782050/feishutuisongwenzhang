from difflib import SequenceMatcher
from config import (
    TOPHUB_HEAT_THRESHOLD,
    TOUTIAO_HEAT_THRESHOLD,
    RANK_RANGE_START,
    RANK_RANGE_END,
    PICK_COUNT,
    DEDUP_THRESHOLD,
)


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
    """按来源独立归一化热度后再综合评分"""
    span = RANK_RANGE_END - RANK_RANGE_START or 1

    for art in articles:
        rank_factor = 1 - (art["rank"] - RANK_RANGE_START) / span
        art["_rank_factor"] = max(0, rank_factor)

    # 按来源分组，各自归一化
    sources = {}
    for art in articles:
        sources.setdefault(art["source"], []).append(art)

    for src, arts in sources.items():
        max_heat = max(a["heat_score"] for a in arts) or 1
        for art in arts:
            art["_normalized_heat"] = art["heat_score"] / max_heat

    # 综合评分
    for art in articles:
        art["score"] = round(
            art["_normalized_heat"] * 0.6 + art["_rank_factor"] * 0.4, 4
        )
        # 清理临时字段
        del art["_normalized_heat"]
        del art["_rank_factor"]

    return articles


def filter_and_pick(tophub_articles: list[dict], toutiao_articles: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    筛选并精选文章。按来源独立归一化热度，避免头条百万级热度碾压微信万级热度。
    返回 (精选列表, 全量归档列表)
    """
    def _filter(art):
        threshold = TOPHUB_HEAT_THRESHOLD if art["source"] == "公众号" else TOUTIAO_HEAT_THRESHOLD
        return (
            art["heat_score"] >= threshold
            and RANK_RANGE_START <= art["rank"] <= RANK_RANGE_END
        )

    tophub_filtered = [a for a in tophub_articles if _filter(a)]
    toutiao_filtered = [a for a in toutiao_articles if _filter(a)]

    all_candidates = _deduplicate(tophub_filtered + toutiao_filtered)

    if not all_candidates:
        return [], []

    all_candidates = _normalize_and_score(all_candidates)
    all_candidates.sort(key=lambda a: a["score"], reverse=True)
    picked = all_candidates[:PICK_COUNT]

    for art in picked:
        art["is_picked"] = True
    for art in all_candidates:
        if "is_picked" not in art:
            art["is_picked"] = False

    return picked, all_candidates
