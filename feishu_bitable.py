import time
import requests
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
BASE_URL = "https://open.feishu.cn/open-apis"

# 字段定义：(名称, 类型, [选项列表])
FIELD_DEFS = [
    ("标题", 1, None),          # 多行文本
    ("来源", 3, ["公众号", "头条"]),       # 单选
    ("排名", 2, None),          # 数字
    ("热度值", 2, None),        # 数字
    ("热度展示", 1, None),      # 文本
    ("原文链接", 15, None),     # 超链接
    ("推送日期", 5, None),      # 日期
    ("早晚班次", 3, ["早间", "晚间"]),     # 单选
    ("是否精选", 7, None),      # 复选框
    ("精选评分", 2, None),      # 数字
]


def _get_token(app_id: str, app_secret: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=15,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取 token 失败: {data}")
    return data["tenant_access_token"]


def _ensure_fields(token: str, app_token: str, table_id: str):
    """确保表格字段存在，不存在则创建"""
    # 检查已有字段
    resp = requests.get(
        f"{BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    existing_names = set()
    if resp.status_code == 200:
        data = resp.json()
        if data.get("code") == 0:
            for item in data.get("data", {}).get("items", []):
                existing_names.add(item.get("field_name", ""))

    # 创建缺失字段
    for field_name, field_type, options in FIELD_DEFS:
        if field_name in existing_names:
            continue
        body = {"field_name": field_name, "type": field_type}
        if options:
            body["property"] = {"options": [{"name": o} for o in options]}

        r = requests.post(
            f"{BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=15,
        )

        # 忽略"字段已存在"错误
        if r.json().get("code") not in (0, 1254005):
            time.sleep(0.3)


def _get_or_create_table(token: str, app_token: str, table_name: str) -> str:
    """获取或创建日期子表，返回 table_id"""
    # 列出所有表，按名称匹配
    resp = requests.get(
        f"{BASE_URL}/bitable/v1/apps/{app_token}/tables",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if resp.status_code == 200 and resp.json().get("code") == 0:
        for item in resp.json().get("data", {}).get("items", []):
            if item.get("name") == table_name:
                return item["table_id"]

    # 不存在则创建
    resp = requests.post(
        f"{BASE_URL}/bitable/v1/apps/{app_token}/tables",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"table": {"name": table_name}},
        timeout=15,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"创建子表失败: {data}")
    return data["data"]["table_id"]


def _build_fields(art: dict) -> dict:
    now = datetime.now(CST)
    return {
        "标题": art.get("title", ""),
        "来源": art.get("source", "公众号"),
        "排名": art.get("rank", 0),
        "热度值": art.get("heat_score", 0),
        "热度展示": art.get("heat_display", ""),
        "原文链接": {
            "link": art.get("url", ""),
            "text": "查看原文",
        },
        "推送日期": int(now.timestamp() * 1000),
        "早晚班次": art.get("session", "早间"),
        "是否精选": art.get("is_picked", False),
        "精选评分": art.get("score", 0),
    }


def archive_to_bitable(app_id: str, app_secret: str, app_token: str, articles: list[dict], session: str):
    if not articles:
        return

    token = _get_token(app_id, app_secret)
    today = datetime.now(CST).strftime("%Y-%m-%d")
    table_id = _get_or_create_table(token, app_token, today)
    _ensure_fields(token, app_token, table_id)

    for art in articles:
        art["session"] = "早间" if session == "morning" else "晚间"

    records = [{"fields": _build_fields(art)} for art in articles]
    batch_size = 500

    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        resp = requests.post(
            f"{BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"records": batch},
            timeout=30,
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Bitable 写入失败: {data}")

        if i + batch_size < len(records):
            time.sleep(0.5)
