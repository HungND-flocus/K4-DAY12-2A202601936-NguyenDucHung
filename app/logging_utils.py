"""CP1 — Structured logging.

`print("client abc hỏi gì đó")` là log cho người đọc. Cloud (Railway, Render,
Cloud Run, Datadog...) đọc log bằng máy: một dòng = một JSON object thì mới
lọc/đếm/cảnh báo được. Đây là khác biệt lớn giữa localhost và production.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone


def utc_now_iso() -> str:
    """CHO SẴN — thời điểm hiện tại theo ISO-8601, múi giờ UTC."""
    return datetime.now(timezone.utc).isoformat()


def emit(event: str, severity: str = "INFO", **fields) -> str:

    """Ghi một dòng log JSON ra stdout.

    TODO (CP1): tạo dict gồm tối thiểu 3 khóa
        - "event"    : tên sự kiện, lấy từ tham số ``event``
        - "severity" : mức log, VIẾT HOA (dùng ``severity.upper()``) — đây là
                       tên khóa mà Google Cloud Logging hiểu để tô màu và lọc
        - "ts"       : ``utc_now_iso()``
    rồi gộp thêm mọi cặp key/value trong ``**fields``.

    In chuỗi JSON đó ra stdout **trên một dòng duy nhất**
    (``json.dumps(..., ensure_ascii=False)``, đừng dùng ``indent``) và
    trả về chính chuỗi đó.

    Ví dụ:
        >>> emit("chat_completed", client_id="sv01", usd_cost=0.0001)
        '{"event": "chat_completed", "severity": "INFO", "ts": "...", ...}'
    """
    record = {
        "event": event,
        "severity": severity.upper(),  # quy ước: severity luôn VIẾT HOA
        "ts": utc_now_iso(),
    }
    # Gộp thêm mọi cặp key/value truyền vào (client_id, usd_cost, ...)
    record.update(fields)

    # Một dòng duy nhất, không indent, giữ nguyên tiếng Việt
    line = json.dumps(record, ensure_ascii=False)
    print(line, file=sys.stdout, flush=True)
    return line