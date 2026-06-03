import os

# ── 飞书 Webhook（卡片推送，不需要应用） ──
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK_URL", "")
FEISHU_WEBHOOK_SECRET = os.environ.get("FEISHU_WEBHOOK_SECRET", "")

# ── 飞书应用（Bitable 归档） ──
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_BITABLE_APP_TOKEN = os.environ.get("FEISHU_BITABLE_APP_TOKEN", "")

# ── 数据源 URL ──
TOPHUB_WEIXIN_URL = "https://tophub.today/n/WnBe01o371"
TOUTIAO_API_URL = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"
DAILYHOT_API_URL = "https://api-hot.imsyy.top/toutiao"

# ── 筛选参数 ──
TOPHUB_HEAT_THRESHOLD = int(os.environ.get("TOPHUB_HEAT_THRESHOLD", "2000"))
TOUTIAO_HEAT_THRESHOLD = int(os.environ.get("TOUTIAO_HEAT_THRESHOLD", "5000"))
RANK_RANGE_START = int(os.environ.get("RANK_RANGE_START", "10"))
RANK_RANGE_END = int(os.environ.get("RANK_RANGE_END", "30"))
PICK_COUNT = int(os.environ.get("PICK_COUNT", "10"))
DEDUP_THRESHOLD = float(os.environ.get("DEDUP_THRESHOLD", "0.8"))

# ── 推送时段 ──
PUSH_SESSION = os.environ.get("PUSH_SESSION", "morning")
