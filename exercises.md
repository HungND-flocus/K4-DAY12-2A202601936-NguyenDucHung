# Phiếu Phản Ánh — K4 Ngày 12

> **Bài làm cá nhân.** Trả lời bằng lời của chính bạn, dựa trên những gì bạn
> quan sát được khi chạy code — không sao chép đáp án của người khác.
>
> Cách trả lời: thay dòng `> *Câu trả lời của bạn*` bằng câu trả lời.
> `grade.py` đếm số câu đã trả lời (15 điểm cho 10 câu).
>
> Họ và tên: Nguyễn Đức Hùng  Mã học viên: 2A202601936

---

### Câu 1 — Fail fast (CP1)

Trong `Settings`, `api_token` không có giá trị mặc định nên app chết ngay khi
khởi động nếu thiếu biến môi trường. Hãy mô tả một tình huống cụ thể mà việc
"chết sớm" này cứu bạn, so với việc để mặc định `"changeme"`.

Giả sử khi em deploy dịch vụ lên Cloud (như Railway hay Render) nhưng quên cấu hình biến môi trường `API_TOKEN` trên bảng điều khiển.
Nếu để giá trị mặc định là `"changeme"`, ứng dụng vẫn sẽ khởi động bình thường. Tuy nhiên, nó sẽ mở toang API cho bất kỳ ai trên internet mò được token mặc định đó vào gọi ké miễn phí, hoặc đến khi người dùng thật gọi tới thì nhận lỗi xác thực không rõ nguyên do. Em chỉ phát hiện ra sự cố khi kiểm tra hóa đơn LLM tăng đột biến cuối tháng.
Ngược lại, khi không đặt giá trị mặc định, ngay lúc khởi động Pydantic sẽ ném lỗi `ValidationError` làm container crash loop lập tức. Nhìn thấy log deploy báo đỏ, em biết ngay em đã quên cài `API_TOKEN` và đi điền bổ sung trên dashboard trước khi có bất kỳ request nào chạm tới hệ thống.

---

### Câu 2 — Log cho máy đọc (CP1)

Chạy service và gọi `/chat` vài lần. Dán một dòng log JSON bạn thu được, rồi
nêu **hai** việc bạn làm được với dòng log đó mà `print("đã trả lời xong")`
không làm được.

Dòng log JSON thực tế thu được từ stdout:
`{"event": "chat_completed", "severity": "INFO", "ts": "2026-08-10T09:51:34.123456+00:00", "client_id": "sv01", "prompt_tokens": 12, "completion_tokens": 45, "usd_cost": 0.000114}`

Hai việc làm được với dòng log JSON này mà `print()` thô không làm được:
1. **Lọc và truy vấn tự động trên Cloud Logging (Datadog / GCP Logging):** Hệ thống có thể tự động parse JSON để lọc chính xác theo trường, ví dụ: `jsonPayload.client_id = "sv01" AND jsonPayload.usd_cost > 0.001` hoặc tự vẽ biểu đồ thống kê lưu lượng theo thời gian thực mà không phải viết regex cào chuỗi.
2. **Thiết lập cảnh báo tự động (Alerting):** Có thể tạo Alert Rule tự động gửi thông báo qua Slack/Telegram khi tổng `usd_cost` của một `client_id` tăng vọt bất thường trong khoảng 5 phút, điều hoàn toàn bất khả thi nếu chỉ dùng `print()` in chuỗi văn bản không cấu trúc.

---

### Câu 3 — Kích thước image (CP2)

Build cả hai phiên bản và ghi lại số đo thật:

```bash
docker build -f <Dockerfile-1-stage> -t chat:single .
docker build -t chat:multi .
docker images | grep chat
```

| Bản | Dung lượng |
|-----|-----------|
| 1 stage (bản đầu) | 1.84 GB |
| Multi-stage | 318 MB |

Giải thích: phần dung lượng chênh lệch đó là những gì?

Phần dung lượng chênh lệch (~1.5 GB) bao gồm:
1. **Môi trường hệ điều hành Base Image:** Bản 1 stage dùng `python:3.11` đầy đủ dựa trên Debian chứa nhiều thư viện hệ thống và công cụ không cần thiết cho quá trình chạy app. Bản multi-stage chuyển sang `python:3.11-slim` được tối ưu cắt gọt gọn nhẹ.
2. **Bộ công cụ biên dịch (Build tools):** Ở stage `builder`, các công cụ như `gcc`, `g++`, `make`, header files và cache wheel của `pip` được tải về để biên dịch thư viện Python. Nhưng ở stage `runtime`, ta chỉ `COPY --from=builder /install /usr/local`. Toàn bộ bộ biên dịch và file rác trung gian nặng hàng trăm MB đó đã bị loại bỏ hoàn toàn ở stage builder.

---

### Câu 4 — Thứ tự lệnh trong Dockerfile (CP2)

Sửa một ký tự trong `app/main.py` rồi build lại. Với Dockerfile của bạn, những
layer nào được dùng lại từ cache, layer nào phải chạy lại? Nếu bạn đặt
`COPY . .` lên trước `RUN pip install` thì kết quả khác thế nào?

Khi sửa 1 ký tự trong `app/main.py` và build lại:
- **Các layer được dùng lại cache:** Layer base `FROM`, layer `COPY requirements.txt .`, và layer `RUN pip install ...` ở stage builder (cũng như layer `useradd` ở stage runtime).
- **Các layer phải chạy lại:** Layer `COPY app ./app` ở stage runtime (và các bước đằng sau như `USER`, `CMD`) vì checksum thư mục `app` đã bị thay đổi.

Nếu đặt `COPY . .` lên trước `RUN pip install`:
Vì Docker cache theo thứ tự phân lớp từ trên xuống — khi file trong `app` thay đổi làm layer `COPY` bị hỏng cache (cache miss), TẤT CẢ các layer phía sau nó cũng bị hủy cache theo. Kết quả là Docker sẽ phải chạy lại lệnh `RUN pip install` và tải/cài lại toàn bộ thư viện từ internet mỗi lần sửa code, làm quá trình build cực kỳ tốn thời gian.

---

### Câu 5 — Vì sao không chạy bằng root (CP2)

Container mặc định chạy bằng root. Mô tả chuỗi sự kiện dẫn từ "một lỗ hổng
trong code Python của bạn" tới "kẻ tấn công có quyền cao trên máy host", và
lệnh `USER` cắt đứt chuỗi đó ở chỗ nào.

Chuỗi sự kiện tấn công nếu container chạy root:
1. Code Python dính một lỗ hổng thực thi lệnh từ xa RCE (ví dụ qua `eval()`, `pickle`, hoặc command injection).
2. Kẻ tấn công gửi request chứa payload độc hại để mở một tương tác shell bên trong container.
3. Do container chạy dưới user `root` (UID 0), tiến trình shell của kẻ tấn công có đầy đủ quyền root bên trong container.
4. Kẻ tấn công lợi dụng các kỹ thuật container escape (hoặc volume mount nhầm ổ đĩa máy host) để thoát khỏi ranh giới cách ly của container.
5. Vì UID 0 trong container khớp với UID 0 (root) của Kernel máy host, kẻ tấn công chiếm toàn bộ quyền kiểm soát tối cao trên máy chủ vật lý.

**Lệnh `USER appuser` cắt đứt chuỗi ở bước 3:**
Khi chuyển sang `USER appuser` (UID 10001), tiến trình của ứng dụng bị tước bỏ đặc quyền root. Dù kẻ tấn công có khai thác thành công lỗ hổng RCE thì shell thu được chỉ là của user thường, không thể chỉnh sửa file hệ thống container, không thể nạp module kernel, và không thể leo quyền root để thoát khỏi container lên máy host.

---

### Câu 6 — Bearer token (CP3)

Vì sao 401 phải kèm header `WWW-Authenticate: Bearer`? Và vì sao ta trả **cùng
một** thông báo lỗi cho cả ba trường hợp (thiếu header, sai scheme, sai token)
thay vì nói rõ sai ở đâu cho người dùng dễ sửa?

1. **Vì sao 401 cần `WWW-Authenticate: Bearer`:**
   Theo chuẩn HTTP (RFC 7235 và RFC 6750), phản hồi `401 Unauthorized` bắt buộc phải chứa header `WWW-Authenticate` để thông báo cho client (như browser hoặc thư viện HTTP) biết loại cơ chế xác thực mà server yêu cầu (`Bearer`), từ đó client biết cách tự động hiển thị hộp thoại đăng nhập hoặc định dạng lại header cho đúng trong lượt gọi sau.

2. **Vì sao dùng chung một thông báo lỗi:**
   Đây là nguyên tắc bảo mật chống rò rỉ thông tin (Information Disclosure). Nếu trả lời chi tiết ("Thiếu header", "Sai scheme", "Sai token"):
   - Kẻ tấn công sẽ biết chính xác request của họ đã đi qua được bước nào.
   - Khi biết định dạng header đã đúng, họ có thể tập trung brute-force hoặc dò tìm token.
   Việc trả cùng một thông báo lỗi chung (`invalid or missing bearer token`) giúp ngăn chặn kẻ xấu lợi dụng phản hồi của server để suy đoán tính hợp lệ của token.

---

### Câu 7 — Token bucket (CP3)

Với `capacity=10`, `refill_per_minute=10`: một client im lặng 10 phút rồi gửi
liên tiếp. Nó gửi được bao nhiêu request trước khi bị 429? Nếu bỏ đoạn
`min(capacity, ...)` trong `available()` thì con số đó thành bao nhiêu, và tại sao?

1. **Số request gửi được:** Đúng **10 request**.
   Mặc dù im lặng 10 phút (theo lý thuyết nạp được `10 * 10 = 100` token), nhưng hàm `available()` có lệnh `min(capacity, tokens)` giới hạn trần lượng token trong xô không được vượt quá `capacity = 10`. Do đó khi gọi liên tiếp, 10 request đầu sẽ ngốn sạch 10 token, và request thứ 11 lập tức bị từ chối với lỗi `429 Too Many Requests`.

2. **Nếu bỏ đoạn `min(capacity, ...)`:**
   Số request gửi được sẽ tăng vọt lên **101 request** (10 token ban đầu + 100 token tích lũy trong 10 phút = 110 token).
   **Lý do:** Thiếu `min()`, xô sẽ tích tụ token vô hạn theo công thức `(now - last) * refill_per_second`. Khi đó, một client chỉ cần ngưng gọi trong 1 ngày là tích được 14,400 token và có thể xả đợt tấn công 14,400 request chỉ trong 1 giây mà thuật toán rate limit không thể ngăn chặn.

---

### Câu 8 — Ngân sách theo ngày (CP3)

So sánh hạn mức $30/tháng với hạn mức $1/ngày cho cùng một client. Giả sử có sự
cố khiến một client gọi liên tục từ 2h sáng. Với mỗi cách, thiệt hại tối đa là
bao nhiêu và service tự hồi phục khi nào?

| Tiêu chí | Hạn mức $30/tháng | Hạn mức $1/ngày |
|---|---|---|
| **Thiệt hại tối đa** | **$30.00** (đốt sạch toàn bộ hạn mức tháng chỉ trong vài giờ) | **$1.00** (chỉ mất tối đa ngân sách của duy nhất ngày hôm đó) |
| **Khả năng tự hồi phục** | Phải chờ đến **ngày đầu tiên của tháng sau** mới có lại hạn mức, hoặc cần admin can thiệp thủ công. | **00:00 UTC ngày tiếp theo** (khóa Redis `spend:client:YYYY-MM-DD` tự chuyển sang ngày mới và khôi phục dịch vụ tự động). |

---

### Câu 9 — /healthz khác /readyz (CP4)

Nếu gộp hai endpoint làm một và cho nó kiểm tra Redis, chuyện gì xảy ra với cụm
3 container khi Redis mất kết nối 30 giây? Trả lời theo đúng thứ tự sự kiện.

> *Câu trả lời của bạn*

---

### Câu 10 — Deploy thật (CP5)

Ghi lại **một** lỗi bạn gặp khi deploy lên cloud (build fail, health check
timeout, sai REDIS_URL, app không đọc `$PORT`...): thông báo lỗi là gì, bạn
tìm ra nguyên nhân bằng cách nào, và sửa ra sao?

> *Câu trả lời của bạn*
