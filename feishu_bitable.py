from datetime import datetime, timezone, timedelta
import lark_oapi as lark
from lark_oapi.api.bitable.v1 import (
    CreateAppTableRequest, CreateAppTableRequestBody, CreateAppTableTable,
    ListAppTableFieldRequest, ListAppTableFieldResponse,
    BatchCreateAppTableRecordRequest, BatchCreateAppTableRecordRequestBody,
    AppTableRecord,
)

CST = timezone(timedelta(hours=8))

FIELDS = [
    ("标题", 1),       # 多行文本
    ("来源", 3),        # 单选
    ("排名", 2),        # 数字
    ("热度值", 2),      # 数字
    ("热度展示", 1),    # 文本
    ("原文链接", 15),   # 超链接
    ("推送日期", 5),    # 日期
    ("早晚班次", 3),    # 单选
    ("是否精选", 7),    # 复选框
    ("精选评分", 2),    # 数字
]


def _get_client(app_id: str, app_secret: str) -> lark.Client:
    return (
        lark.Client.builder()
        .app_id(app_id)
        .app_secret(app_secret)
        .log_level(lark.LogLevel.INFO)
        .build()
    )


def _get_or_create_table(client: lark.Client, app_token: str, table_name: str) -> str:
    """获取已存在的日期子表，不存在则创建，返回 table_id"""
    # 先查已有表
    req = ListAppTableFieldRequest.builder().app_token(app_token).table_id(table_name).build()
    resp = client.bitable.v1.app_table_field.list(req)
    if resp.success():
        return table_name

    # 不存在则创建
    req = (
        CreateAppTableRequest.builder()
        .app_token(app_token)
        .request_body(
            CreateAppTableRequestBody.builder()
            .table(CreateAppTableTable.builder().name(table_name).build())
            .build()
        )
        .build()
    )
    resp = client.bitable.v1.app_table.create(req)
    if not resp.success():
        raise RuntimeError(f"创建子表失败: {resp.msg} ({resp.code})")

    return resp.data.table_id


def _article_to_record(art: dict) -> AppTableRecord:
    """将文章 dict 转为 Bitable 记录"""
    now = datetime.now(CST)

    fields = {
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

    return AppTableRecord.builder().fields(fields).build()


def archive_to_bitable(app_id: str, app_secret: str, app_token: str, articles: list[dict], session: str):
    """将全量文章归档到飞书多维表格"""
    if not articles:
        return

    client = _get_client(app_id, app_secret)
    today = datetime.now(CST).strftime("%Y-%m-%d")
    table_id = _get_or_create_table(client, app_token, today)

    for art in articles:
        art["session"] = "早间" if session == "morning" else "晚间"

    # 批量写入（单次最多 500 条）
    records = [_article_to_record(art) for art in articles]
    batch_size = 500

    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        req = (
            BatchCreateAppTableRecordRequest.builder()
            .app_token(app_token)
            .table_id(table_id)
            .request_body(
                BatchCreateAppTableRecordRequestBody.builder()
                .records(batch)
                .build()
            )
            .build()
        )
        resp = client.bitable.v1.app_table_record.batch_create(req)
        if not resp.success():
            raise RuntimeError(f"Bitable 写入失败: {resp.msg} ({resp.code})")
