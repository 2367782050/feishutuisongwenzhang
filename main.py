import sys
from config import (
    FEISHU_WEBHOOK_URL,
    FEISHU_WEBHOOK_SECRET,
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    FEISHU_BITABLE_APP_TOKEN,
    PUSH_SESSION,
)
from fetcher_tophub import fetch_tophub_weixin, fetch_zhihu, fetch_36kr, fetch_weibo
from fetcher_toutiao import fetch_toutiao
from filter_articles import filter_and_pick
from feishu_sender import send_card, send_error_notification
from feishu_bitable import archive_to_bitable
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
    print(f"[{PUSH_SESSION}] 开始拉取数据...")

    tophub_articles = []
    toutiao_articles = []
    all_raw = []

    # 拉取各平台
    fetchers = [
        ("公众号", fetch_tophub_weixin),
        ("头条", fetch_toutiao),
        ("知乎", fetch_zhihu),
        ("36氪", fetch_36kr),
        ("微博", fetch_weibo),
    ]

    for name, fetcher in fetchers:
        try:
            articles = fetcher()
            all_raw.extend(articles)
            if name == "头条":
                toutiao_articles = articles
            else:
                tophub_articles.extend(articles)
            print(f"  {name}: {len(articles)} 条")
        except Exception as e:
            print(f"  {name} 拉取失败: {e}")

    # 所有源都失败 → 发异常通知
    if not all_raw:
        msg = "所有数据源均无法访问"
        print(f"  ❌ {msg}")
        try:
            send_error_notification(FEISHU_WEBHOOK_URL, FEISHU_WEBHOOK_SECRET, msg)
        except Exception:
            pass
        sys.exit(1)

    # 筛选精选 + 全量
    picked, all_articles = filter_and_pick(tophub_articles, toutiao_articles)
    print(f"  精选: {len(picked)} 条, 全量归档: {len(all_articles)} 条")

    # 生成亮点标签
    batch_generate_teasers(picked)
    batch_generate_teasers(all_articles)

    # 通道 1：推送卡片到飞书群
    if picked:
        try:
            send_card(FEISHU_WEBHOOK_URL, FEISHU_WEBHOOK_SECRET, picked, PUSH_SESSION)
            print("  ✅ 飞书卡片已发送")
        except Exception as e:
            print(f"  ❌ 飞书卡片发送失败: {e}")
    else:
        print("  ⚠️ 无文章可推送（筛选后为空）")

    # 通道 2：归档到多维表格
    if all_articles:
        try:
            archive_to_bitable(
                FEISHU_APP_ID,
                FEISHU_APP_SECRET,
                FEISHU_BITABLE_APP_TOKEN,
                all_articles,
                PUSH_SESSION,
            )
            print("  ✅ 多维表格已归档")
        except Exception as e:
            print(f"  ❌ 多维表格归档失败: {e}")

    print(f"[{PUSH_SESSION}] 完成")


if __name__ == "__main__":
    main()
