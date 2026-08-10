# Hướng Dẫn Cách Làm & Giải Thích Chi Tiết — Checkpoint 2

Checkpoint 2 tập trung vào kỹ thuật đóng gói container chuyên nghiệp (Containerization) và bảo mật Docker image cho môi trường Production:
1. **Tối ưu Multi-Stage Build & Image Size** trong [Dockerfile](file:///d:/VinAI%20in%20Action/VinAI%20Lab/K4-DAY12-2A202601936-NguyenDucHung/Dockerfile)
2. **Loại bỏ các file không cần thiết / nhạy cảm** trong [.dockerignore](file:///d:/VinAI%20in%20Action/VinAI%20Lab/K4-DAY12-2A202601936-NguyenDucHung/.dockerignore)
3. **Quản lý đa container (Stack Orchestration)** trong [docker-compose.yml](file:///d:/VinAI%20in%20Action/VinAI%20Lab/K4-DAY12-2A202601936-NguyenDucHung/docker-compose.yml)

---

## 1. Tối Ưu Dockerfile Multi-Stage (`Dockerfile`)

### 💡 Nguyên lý Multi-Stage Build
- Image đơn stage thông thường chứa cả công cụ biên dịch (`gcc`, `build-essential`, cache pip...) làm dung lượng image phình to (từ 1.2GB đến 1.8GB).
- **Multi-Stage Build** chia quá trình thành 2 stage:
  - **Stage Builder:** Cài đặt các thư viện vào một thư mục tạm thời.
  - **Stage Runtime:** Chỉ copy kết quả cài đặt sang một Base Image mỏng (`slim` hoặc `alpine`). Bỏ lại toàn bộ compiler. Giúp dung lượng image giảm xuống dưới **400MB**.

### 🛠️ Cách cài đặt trong `Dockerfile`

```dockerfile
# ── Stage 1: Builder ──
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ──
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy các package đã cài từ stage builder sang /usr/local
COPY --from=builder /install /usr/local

# Tạo user thường không có quyền root
RUN useradd --create-home --uid 10001 appuser

COPY app ./app
COPY utils ./utils

# Chuyển sang chạy bằng user thường
USER appuser

EXPOSE 8000

# Healthcheck định kỳ 30s
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz').read()" || exit 1

# Khởi động ứng dụng với cổng động ${PORT:-8000}
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

### 🔒 Các điểm bảo mật & hiệu năng cốt lõi:
1. **Tận dụng Docker Layer Cache:** `COPY requirements.txt` và `pip install` nằm TRƯỚC khi `COPY app`. Khi sửa 1 dòng code Python, Docker tận dụng cache layer thư viện nên không phải cài lại `requirements.txt`.
2. **Không chạy bằng Root (`USER appuser`):** Tránh trường hợp nếu ứng dụng bị chiếm quyền kiểm soát (remote code execution), kẻ tấn công sẽ có quyền root trên máy host.
3. **HEALTHCHECK:** Giúp Docker/Cloud phát hiện và khởi động lại container nếu ứng dụng bị treo.

---

## 2. Loại Bỏ File Nhạy Cảm (`.dockerignore`)

### 💡 Vì sao cần `.dockerignore`?
- Ngăn ngừa vô tình `COPY . .` mang file `.env` (chứa API key, password) vào trong Docker Image công khai.
- Giảm dung lượng build context (bỏ qua `.git`, `.venv`, `__pycache__`).

### 🛠️ Nội dung `.dockerignore`

```text
.env
.env.example
__pycache__
*.pyc
.git
.gitignore
.venv
tests
screenshots
exercises.md
LAB_GUIDE.md
README.md
DEPLOYMENT.md
grade.py
```

*Lưu ý:* Tuyệt đối không đưa các thư mục/file như `app/`, `utils/`, `requirements.txt` vào file này.

---

## 3. Cấu Hình Docker Compose Stack (`docker-compose.yml`)

### 🛠️ Cách cài đặt trong `docker-compose.yml`

```yaml
services:
  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  chat:
    build: .
    ports:
      - "8000:8000"
    environment:
      API_TOKEN: ${API_TOKEN}
      REDIS_URL: redis://redis:6379/0
      PORT: 8000
    depends_on:
      - redis
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz').read()"]
      interval: 10s
      timeout: 5s
      retries: 3

volumes:
  redis-data:
```

### ⚠️ Lưu ý quan trọng về Networking trong Compose:
- Trong Docker Compose, **tên service chính là hostname**. Vì vậy `REDIS_URL` phải là `redis://redis:6379/0` chứ không phải `redis://localhost:6379/0` (`localhost` bên trong container chính là bản thân container đó).
- `API_TOKEN: ${API_TOKEN}` giúp Docker Compose đọc tự động từ file `.env` mà không làm lộ secret trong file yml.

---

## 4. Kiểm Thử & Xác Nhận

```powershell
pytest tests/test_cp2.py -v
python grade.py --no-bonus
```

**Kết quả:** Pass 14/14 test cases cấu trúc, đạt **15.0 / 15.0 điểm**.
