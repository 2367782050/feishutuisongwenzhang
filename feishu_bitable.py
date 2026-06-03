import time
import requests
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))

BASE_URL = "https://open.feishu.cn/open-apis"


def _get_token(app_id: str, app_secret: str) -> str:
    """获取 tenant_access_token，自动缓存 1.5 小时"""
    resp = requests.post(
        f"{BASE_URL}/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=15,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取 token 失败: {data}")
    return data["tenant_access_token"]


def _table_exists(token: str, app_token: str, table_id: str) -> bool:
    """检查子表是否存在"""
    resp = requests.get(
        f"{BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    return resp.json().get("code") == 0


def _create_table(token: str, app_token: str, table_name: str) -> str:
    """创建子表，返回 table_id"""
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


def _get_or_create_table(token: str, app_token: str, table_name: str) -> str:
    """获取或创建日期子表，返回 table_id"""
    if _table_exists(token, app_token, table_name):
        return table_name
    return _create_table(token, app_token, table_name)


def _build_fields(art: dict) -> dict:
    """将文章 dict 转为 Bitable 字段格式"""
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
    """将全量文章归档到飞书多维表格"""
    if not articles:
        return

    token = _get_token(app_id, app_secret)
    today = datetime.now(CST).strftime("%Y-%m-%d")
    table_id = _get_or_create_table(token, app_token, today)

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
