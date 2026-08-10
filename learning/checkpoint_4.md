# Hướng Dẫn Cách Làm & Giải Thích Chi Tiết — Checkpoint 4

Checkpoint 4 hướng tới tiêu chuẩn nâng cao về độ tin cậy và khả năng mở rộng ngang (Scaling & Reliability):
1. **Dịch vụ Không Lưu Trạng Thái Trong Memory (Stateless Architecture)** trong [app/store.py](file:///d:/VinAI%20in%20Action/VinAI%20Lab/K4-DAY12-2A202601936-NguyenDucHung/app/store.py)
2. **Kiểm Tra Trạng Thái Sẵn Sàng (Readiness Probe `/readyz`)** trong [app/main.py](file:///d:/VinAI%20in%20Action/VinAI%20Lab/K4-DAY12-2A202601936-NguyenDucHung/app/main.py)
3. **Tắt Ứng Dụng Mượt Mà (Graceful Shutdown & Draining)** trong [app/lifecycle.py](file:///d:/VinAI%20in%20Action/VinAI%20Lab/K4-DAY12-2A202601936-NguyenDucHung/app/lifecycle.py)

---

## 1. Kiến Trúc Stateless (`app/store.py`)

### 💡 Nguyên lý Stateless
- Trong mô hình phân tán (Scale ngang ra 3-5 container đằng sau Load Balancer), một client gửi request 1 vào Container A và request 2 vào Container B.
- Nếu lưu lịch sử hội thoại trong bộ nhớ RAM (`chat_history = {}`), Container B sẽ không thấy dữ liệu của Container A, dẫn tới hiện tượng "mất trí nhớ ngẫu nhiên".
- **Giải pháp:** Đưa toàn bộ state ra ngoài tiến trình ứng dụng vào **Redis Centralized Store**. Tất cả container đều truy vấn chung tới Redis.

### 🛠️ Cấu trúc dữ liệu Redis List (`chat:<client_id>`)

```python
import json
import redis

HISTORY_MAX_MESSAGES = 12
HISTORY_TTL_SECONDS = 3 * 24 * 3600

class ChatStore:
    def __init__(self, client) -> None:
        self.client = client

    def ping(self) -> bool:
        """Kiểm tra Redis có phản hồi không mà không ném Exception."""
        try:
            return bool(self.client.ping())
        except Exception:
            return False

    def add_turn(self, client_id: str, role: str, content: str) -> None:
        key = f"chat:{client_id}"
        # 1. Thêm tin nhắn mới vào cuối danh sách Redis
        self.client.rpush(key, json.dumps({"role": role, "content": content}, ensure_ascii=False))
        # 2. Cắt chỉ giữ tối đa 12 tin nhắn gần nhất (-12 đến -1) để tránh phình prompt
        self.client.ltrim(key, -HISTORY_MAX_MESSAGES, -1)
        # 3. Đặt thời gian hết hạn (TTL) 3 ngày
        self.client.expire(key, HISTORY_TTL_SECONDS)

    def history(self, client_id: str) -> list[dict]:
        key = f"chat:{client_id}"
        items = self.client.lrange(key, 0, -1)
        if not items:
            return []
        return [json.loads(item) for item in items]
```

---

## 2. Readiness Probe `/readyz` (`app/main.py`)

### 💡 Khái niệm `/readyz` vs `/healthz`

| Tiêu chí | Liveness Probe (`/healthz`) | Readiness Probe (`/readyz`) |
|---|---|---|
| **Mục đích** | Kiểm tra container có còn sống không? | Kiểm tra container đã sẵn sàng nhận traffic chưa? |
| **Kiểm tra Dependency** | **KHÔNG** (Tuyệt đối không chạm vào Redis/DB) | **CÓ** (Gọi `store.ping()` kiểm tra kết nối Redis) |
| **Khi trả về 503** | Orchestrator sẽ **KILL & RESTART** container | Load Balancer **NGỪNG ĐẨY TRAFFIC** vào, không restart container |

### 🛠️ Cách cài đặt `/readyz`

```python
@app.get("/readyz")
def readyz(store: ChatStore = Depends(get_store)):
    if shutdown_guard.draining:
        return JSONResponse(
            status_code=503,
            content={"status": "draining"},
        )
    if not store.ping():
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "redis": False},
        )
    return {"status": "ready", "redis": True}
```

---

## 3. Graceful Shutdown & Draining (`app/lifecycle.py`)

### 💡 Quy trình Draining khi Deploy phiên bản mới
1. Khi deploy code mới, Orchestrator gửi tín hiệu **`SIGTERM`** tới container cũ.
2. Signal handler lập tức bật cờ `draining = True`.
3. `/healthz` và `/readyz` phản hồi `503 {"status": "draining"}` -> Load Balancer rút container cũ ra khỏi vòng xoay phân phối request.
4. Container xử lý nốt các request đang chạy dở rồi tự động thoát mượt mà mà không làm ngắt kết nối của user (không bị 502/504).
5. **Quan trọng:** Phải chuyển tiếp tín hiệu lại cho handler mặc định của Uvicorn để tiến trình server biết cách dừng lại.

### 🛠️ Cách cài đặt trong `app/lifecycle.py`

```python
import signal

class ShutdownGuard:
    def __init__(self) -> None:
        self.draining = False
        self._previous: dict = {}

    def start_draining(self, signum=None, frame=None) -> None:
        self.draining = True
        # Gọi lại handler trước đó của uvicorn để dừng server
        previous = self._previous.get(signum)
        if callable(previous):
            previous(signum, frame)

    def arm(self) -> None:
        for sig in (signal.SIGTERM, signal.SIGINT):
            self._previous[sig] = signal.getsignal(sig) # Lưu handler cũ
            signal.signal(sig, self.start_draining)    # Ghi đè handler mới

shutdown_guard = ShutdownGuard()
```

---

## 4. Kiểm Thử & Kết Quả

```powershell
pytest tests/test_cp4.py -v
python grade.py --no-bonus
```

**Kết quả:** Pass **19/19 test cases**, đạt **20.0 / 20.0 điểm tối đa**.
