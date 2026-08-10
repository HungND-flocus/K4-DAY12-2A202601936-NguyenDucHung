# Hướng Dẫn Cách Làm & Giải Thích Chi Tiết — Checkpoint 1

Checkpoint 1 tập trung vào 3 trụ cột cơ bản của một microservice chuẩn production theo triết lý **12-Factor App**:
1. **Cấu hình độc lập (12-Factor Config)** trong [app/config.py](file:///d:/VinAI%20in%20Action/VinAI%20Lab/K4-DAY12-2A202601936-NguyenDucHung/app/config.py)
2. **Ghi log có cấu trúc (Structured JSON Logging)** trong [app/logging_utils.py](file:///d:/VinAI%20in%20Action/VinAI%20Lab/K4-DAY12-2A202601936-NguyenDucHung/app/logging_utils.py)
3. **Kiểm tra trạng thái sống (Liveness Probe `/healthz`)** trong [app/main.py](file:///d:/VinAI%20in%20Action/VinAI%20Lab/K4-DAY12-2A202601936-NguyenDucHung/app/main.py)

---

## 1. Cấu Hình 12-Factor App (`app/config.py`)

### 💡 Nguyên lý 12-Factor: Config nằm ngoài Code
- Code là thứ giống nhau ở mọi môi trường (Laptop, Staging, Production).
- Config (port, database URL, secret tokens) thay đổi theo từng môi trường và **bắt buộc truyền qua biến môi trường (Environment Variables)**.
- **Tuyệt đối không hardcode Secret**: Nộp mã token/API key lên Git là rủi ro bảo mật nghiêm trọng.

### 🛠️ Cách cài đặt trong `app/config.py`

Khai báo class `Settings` kế thừa từ `pydantic_settings.BaseSettings`:

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    port: int = 8000
    api_token: str                               # BẮT BUỘC — Không có giá trị mặc định!
    redis_url: str = "redis://localhost:6379/0"
    bucket_capacity: int = 10
    refill_per_minute: int = 10
    daily_budget_usd: float = 1.0
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

### ❓ Vì sao `api_token` KHÔNG có giá trị mặc định?
- **Fail-Fast (Chết sớm):** Nếu quên cấu hình `API_TOKEN` trên Cloud, ứng dụng sẽ báo lỗi `ValidationError` ngay lúc khởi động (build/deploy phase) thay vì khởi động thành công với token mặc định để rồi bị kẻ xấu lợi dụng hoặc phát hiện sau khi nhận hóa đơn chi phí.

---

## 2. Ghi Log Cấu Trúc JSON (`app/logging_utils.py`)

### 💡 Vì sao dùng JSON Log thay vì `print()` thường?
- `print("User A đã gọi API")` chỉ dành cho con người đọc trên máy cá nhân.
- Trên Cloud (Google Cloud Logging, Datadog, AWS CloudWatch), các hệ thống tự động gom log theo dòng stdout. Format **JSON 1 dòng** cho phép tìm kiếm, lọc theo trường (`severity`, `client_id`), và thiết lập cảnh báo tự động.

### 🛠️ Cách cài đặt trong `app/logging_utils.py`

```python
import json
import sys
from datetime import datetime, timezone

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def emit(event: str, severity: str = "INFO", **fields) -> str:
    record = {
        "event": event,
        "severity": severity.upper(),   # Bắt buộc VIẾT HOA (INFO, ERROR, WARN)
        "ts": utc_now_iso(),            # Thời gian dạng ISO-8601 UTC
    }
    record.update(fields)               # Gộp thêm các trường động (client_id, usd_cost...)

    # dumps dạng 1 dòng duy nhất, không indent, giữ unicode tiếng Việt
    line = json.dumps(record, ensure_ascii=False)
    print(line, file=sys.stdout, flush=True)
    return line
```

### ⚠️ Lưu ý quan trọng:
1. `severity` phải **VIẾT HOA** (`.upper()`): Các công cụ Cloud Log như Google Cloud Parsing dựa vào khóa `severity` viết hoa để tô màu log (Đỏ: ERROR, Vàng: WARNING, Xanh: INFO).
2. **Nằm gọn trên 1 dòng duy nhất**: Không được dùng `indent=2`. Ngắt dòng sẽ khiến Cloud xem mỗi dòng là một log item độc lập, làm vỡ dữ liệu.

---

## 3. Liveness Probe `/healthz` (`app/main.py`)

### 💡 Khái niệm `/healthz` (Liveness Probe)
- Trả lời câu hỏi: *"Container/Process này còn sống không? Có cần restart lại container không?"*

### 🛠️ Cách cài đặt trong `app/main.py`

```python
@app.get("/healthz")
def healthz():
    if shutdown_guard.draining:
        return JSONResponse(
            status_code=503,
            content={"status": "draining"},
        )
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
    }
```

### ⚠️ Quy tắc sống còn của `/healthz`:
- **KHÔNG được gọi Redis, DB hay bất kỳ dịch vụ bên ngoài nào!**
- Nếu `/healthz` kiểm tra Redis, khi Redis chập chờn 5 giây, toàn bộ các container Chat Service sẽ bị orchestrator (Docker/Kubernetes) đánh dấu unhealthy và restart đồng loạt — làm biến một sự cố nhỏ thành sập toàn hệ thống.
- Việc kiểm tra kết nối hạ tầng phụ thuộc thuộc về **Readiness Probe (`/readyz`)** ở Checkpoint 4.

---

## 4. Hướng Dẫn Kiểm Thử (Verification)

Chạy câu lệnh test dành riêng cho Checkpoint 1:

```powershell
pytest tests/test_cp1.py -v
```

Hoặc chạy script chấm điểm tự động:

```powershell
python grade.py --no-bonus
```

**Kết quả mong đợi:** Pass 13/13 test cases, đạt **15.0 / 15.0 điểm**.
