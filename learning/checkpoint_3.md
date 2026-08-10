# Hướng Dẫn Cách Làm & Giải Thích Chi Tiết — Checkpoint 3

Checkpoint 3 tập trung vào 3 lớp bảo vệ tài nguyên API (API Security) trước khi gọi tới mô hình LLM:
1. **Xác thực Bearer Token (Authentication - RFC 6750)** trong [app/auth.py](file:///d:/VinAI%20in%20Action/VinAI%20Lab/K4-DAY12-2A202601936-NguyenDucHung/app/auth.py)
2. **Rate Limiting theo Thuật Toán Token Bucket** trong [app/rate_limiter.py](file:///d:/VinAI%20in%20Action/VinAI%20Lab/K4-DAY12-2A202601936-NguyenDucHung/app/rate_limiter.py)
3. **Giới Hạn Ngân Sách Theo Ngày (Cost Guard)** trong [app/cost_guard.py](file:///d:/VinAI%20in%20Action/VinAI%20Lab/K4-DAY12-2A202601936-NguyenDucHung/app/cost_guard.py)
4. **Tích hợp vào Route `/chat`** trong [app/main.py](file:///d:/VinAI%20in%20Action/VinAI%20Lab/K4-DAY12-2A202601936-NguyenDucHung/app/main.py)

---

## 1. Bearer Token Authentication (`app/auth.py`)

### 💡 Khái niệm & Chuẩn RFC 6750
- Khi công khai URL API, bất kỳ ai cũng có thể gửi request. Nếu không có xác thực, chi phí LLM sẽ nổ tung do bot quét hoặc người lạ gọi tự do.
- Token được gửi trong HTTP Header: `Authorization: Bearer <token>`.
- Client có thể gửi kèm `X-Client-Id: <id>` để định danh thiết bị/người dùng. Nếu không có, mặc định là `"anonymous"`.

### 🛠️ Cách cài đặt trong `app/auth.py`

```python
import secrets
from fastapi import Header, HTTPException, status
from .config import get_settings

ANONYMOUS_CLIENT = "anonymous"
SCHEME = "Bearer"

def verify_bearer_token(
    authorization: str | None = Header(default=None),
    x_client_id: str | None = Header(default=None),
) -> str:
    # 1. Thiếu header Authorization -> 401
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Tách Scheme và Token -> kiểm tra scheme case-insensitive
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != SCHEME.lower() or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. So sánh Token bằng secrets.compare_digest (Chống Timing Attack)
    if not secrets.compare_digest(token, get_settings().api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return x_client_id if x_client_id else ANONYMOUS_CLIENT
```

### 🔒 Vì sao dùng `secrets.compare_digest` thay vì `==`?
- Toán tử `==` dừng ngay tại ký tự sai đầu tiên, khiến thời gian phản hồi thay đổi tùy thuộc vào độ dài ký tự đúng. Kẻ tấn công có thể đo thời gian để dò từng ký tự của token (Timing Attack).
- `secrets.compare_digest` luôn thực hiện so sánh với thời gian cố định.

---

## 2. Rate Limiting — Token Bucket (`app/rate_limiter.py`)

### 💡 Nguyên lý Token Bucket
- Mỗi `client_id` sở hữu một cái "xô" chứa tối đa `capacity` token.
- Token được nạp lại tự động đều đặn theo thời gian với tốc độ `refill_per_second`.
- Mỗi request tiêu tốn **1 token**. Nếu xô không đủ token (< 1), server ném lỗi `429 Too Many Requests` kèm Header `Retry-After`.
- **Ưu điểm:** Cho phép user gửi dồn request trong thời gian ngắn (burst limit) nhưng vẫn chặn kẻ tấn công xả request liên tục.

### 🛠️ Cấu trúc dữ liệu Redis Hash (`bucket:<client_id>`)

```python
class TokenBucket:
    def available(self, client_id: str, now: float | None = None) -> float:
        now = now if now is not None else time.time()
        key = self._key(client_id)
        state = self.client.hgetall(key)
        if not state:
            return float(self.capacity)

        tokens = float(state["tokens"])
        last = float(state["ts"])
        # Cộng thêm số token tự nạp lại theo khoảng thời gian đã trôi qua
        tokens += (now - last) * self.refill_per_second
        return min(float(self.capacity), tokens)  # Không vượt quá sức chứa

    def consume(self, client_id: str, now: float | None = None) -> None:
        now = now if now is not None else time.time()
        key = self._key(client_id)
        tokens = self.available(client_id, now)
        if tokens < 1:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate limit exceeded",
                headers={"Retry-After": str(self.retry_after(tokens))},
            )

        self.client.hset(key, mapping={"tokens": tokens - 1, "ts": now})
        self.client.expire(key, BUCKET_TTL_SECONDS)
```

---

## 3. Cost Guard — Hạn Mức Ngân Sách Theo Ngày (`app/cost_guard.py`)

### 💡 Vì sao giới hạn theo ngày?
- Một request 50k token tốn nhiều chi phí hơn hàng trăm request ngắn.
- Chốt ngân sách theo ngày (`spend:<client_id>:<YYYY-MM-DD>`) giúp giới hạn thiệt hại tối đa nếu xảy ra sự cố và tự động khôi phục vào ngày hôm sau.
- Nếu vượt quá ngân sách ngày -> ném lỗi `402 Payment Required`.

### 🛠️ Cách cài đặt trong `app/cost_guard.py`

```python
class CostGuard:
    def spent(self, client_id: str, day: str | None = None) -> float:
        val = self.client.get(self._key(client_id, day))
        return float(val) if val is not None else 0.0

    def check(self, client_id: str, estimated_cost: float = 0.0, day: str | None = None) -> None:
        if self.spent(client_id, day) + estimated_cost > self.budget:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="daily budget exceeded",
            )

    def record(self, client_id: str, cost: float, day: str | None = None) -> float:
        key = self._key(client_id, day)
        total = self.client.incrbyfloat(key, cost)
        self.client.expire(key, KEY_TTL_SECONDS)
        return float(total)
```

---

## 4. Tích Hợp Vào Route `/chat` (`app/main.py`)

### ⚠️ Thứ tự xử lý bắt buộc trong Route `/chat`:
1. `verify_bearer_token` (FastAPI Dependency) -> Lấy `client_id` (Nếu sai -> `401`).
2. `bucket.consume(client_id)` -> Kiểm tra Token Bucket (Nếu hết -> `429`).
3. `guard.check(client_id)` -> Kiểm tra ngân sách ngày (Nếu hết -> `402`).
4. `store.history(client_id)` -> Lấy lịch sử hội thoại.
5. `generate_reply(...)` -> Gọi LLM tạo phản hồi.
6. `store.add_turn(...)` -> Ghi tin nhắn user & assistant vào lịch sử.
7. `guard.record(client_id, cost)` -> Cộng dồn chi phí.
8. `emit("chat_completed", ...)` -> Ghi log JSON.

---

## 5. Kiểm Thử & Kết Quả

```powershell
pytest tests/test_cp3.py -v
python grade.py --no-bonus
```

**Kết quả:** Pass **29/29 test cases**, đạt **20.0 / 20.0 điểm tối đa**.
