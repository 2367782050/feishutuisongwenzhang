import os

# ── 飞书 Webhook（卡片推送） ──
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK_URL", "")
FEISHU_WEBHOOK_SECRET = os.environ.get("FEISHU_WEBHOOK_SECRET", "")

# ── 飞书应用（Bitable 归档） ──
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_BITABLE_APP_TOKEN = os.environ.get("FEISHU_BITABLE_APP_TOKEN", "")

# ── 筛选参数 ──
HEAT_THRESHOLD = int(os.environ.get("HEAT_THRESHOLD", "2000"))
PICK_COUNT = int(os.environ.get("PICK_COUNT", "35"))
DEDUP_THRESHOLD = float(os.environ.get("DEDUP_THRESHOLD", "0.8"))
