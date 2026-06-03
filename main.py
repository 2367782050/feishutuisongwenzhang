import sys
from config import (
    FEISHU_WEBHOOK_URL,
    FEISHU_WEBHOOK_SECRET,
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    FEISHU_BITABLE_APP_TOKEN,
)
from fetcher_tophub import fetch_tophub_weixin
from filter_articles import filter_and_pick
from feishu_sender import send_card, send_error_notification
from feishu_bitable import archive_to_bitable, get_recent_titles
from fetcher_summary import batch_generate_teasers

REQUIRED_ENV = {
    "FEISHU_WEBHOOK_URL": FEISHU_WEBHOOK_URL,
    "FEISHU_APP_ID": FEISHU_APP_ID,
    "FEISHU_APP_SECRET": FEISHU_APP_SECRET,
    "FEISHU_BITABLE_APP_TOKEN": FEISHU_BITABLE_APP_TOKEN,
}


def _validate_env():
    missing = [k for k, v in REQUIRED_ENV.items() if not v]
    if missing:
        print(f"❌ 缺少必需的环境变量: {', '.join(missing)}")
        print("请设置对应的 GitHub Secrets 或 .env 文件")
        sys.exit(1)


def main():
    _validate_env()
    print("开始拉取公众号热文...")

    # 拉取公众号
    try:
        articles = fetch_tophub_weixin()
        print(f"  公众号: {len(articles)} 条")
    except Exception as e:
        print(f"  ❌ 拉取失败: {e}")
        try:
            send_error_notification(FEISHU_WEBHOOK_URL, FEISHU_WEBHOOK_SECRET, str(e))
        except Exception:
            pass
        sys.exit(1)

    if not articles:
        msg = "公众号数据源无数据"
        print(f"  ❌ {msg}")
        send_error_notification(FEISHU_WEBHOOK_URL, FEISHU_WEBHOOK_SECRET, msg)
        sys.exit(1)

    # 获取近 7 天已推送标题（跨天去重）
    recent_titles = []
    try:
        recent_titles = get_recent_titles(
            FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_BITABLE_APP_TOKEN, days=7
        )
        print(f"  去重库: {len(recent_titles)} 条历史标题")
    except Exception as e:
        print(f"  去重库查询失败（跳过）: {e}")

    # 赛道筛选
    picked, all_articles = filter_and_pick(articles, [], recent_titles)
    print(f"  精选: {len(picked)} 条 ({_cat_summary(picked)})")
    print(f"  全量归档: {len(all_articles)} 条")

    # 生成亮点标签
    batch_generate_teasers(picked)
    batch_generate_teasers(all_articles)

    # 推送卡片
    if picked:
        try:
            send_card(FEISHU_WEBHOOK_URL, FEISHU_WEBHOOK_SECRET, picked, "morning")
            print("  ✅ 飞书卡片已发送")
        except Exception as e:
            print(f"  ❌ 飞书卡片发送失败: {e}")
    else:
        print("  ⚠️ 无文章可推送")

    # 归档多维表格
    if all_articles:
        try:
            archive_to_bitable(
                FEISHU_APP_ID, FEISHU_APP_SECRET,
                FEISHU_BITABLE_APP_TOKEN, all_articles, "morning",
            )
            print("  ✅ 多维表格已归档")
        except Exception as e:
            print(f"  ❌ 多维表格归档失败: {e}")

    print("完成")


def _cat_summary(articles: list[dict]) -> str:
    """统计各赛道数量"""
    from collections import Counter
    cats = Counter()
    for a in articles:
        tags = a.get("quality_tags", [])
        for t in tags:
            if t not in ("blocked", "低质信号", "优质信号", "其他"):
                cats[t] += 1
                break
    return " | ".join(f"{c}×{n}" for c, n in cats.most_common())


if __name__ == "__main__":
    main()
