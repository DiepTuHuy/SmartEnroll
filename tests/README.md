# Test SmartEnroll

Mọi test chạy trên **cổng trường giả**, không gửi gì tới cổng trường thật, và dùng thư mục HOME tạm nên không đụng tới file cấu hình thật của bạn.

## Test chức năng (khoảng 1 phút)

```bash
venv/bin/python tests/run_all.py
```

| File | Kiểm tra |
|---|---|
| `test_overload.py` | Đăng nhập và spam khi cổng trường quá tải: không nhận kết nối, xử lý quá lâu, 502/503, trả trang HTML, token hết hạn giữa chừng, sai mật khẩu, bấm dừng |
| `test_heartbeat.py` | Treo máy lâu: heartbeat phát hiện token bị cổng trường hủy và đăng nhập lại khi cổng còn vắng |
| `test_flask_api.py` | API của `server.py`: đăng nhập nền, trạng thái, cấu hình thủ công, đăng xuất, thông báo lỗi 403 |

## Load test nhiều tài khoản (khoảng 2–3 phút)

```bash
venv/bin/python tests/load_test.py --accounts 1000
```

Dựng một cổng trường giả **chạy như server thật** (`fake_portal_server.py`, tiến trình riêng, kết nối TCP thật):

- chỉ xử lý được 60 request cùng lúc, tối đa 600 request đứng chờ, quá thì trả 503
- hàng chờ kết nối TCP có hạn, nên khi dồn dập sẽ bị timeout kết nối như thật
- ngẫu nhiên ngắt kết nối giữa chừng, trả 502, hủy token đang dùng
- 30 lớp × 30 chỗ; vài lớp đông người chọn hơn hẳn; mở đăng ký sau 45 giây

Sau đó cho 1000 tài khoản giả **cùng đăng nhập một lúc**, rồi **cùng spam đăng ký** từ trước giờ mở. 20% dùng Turbo, 10 tài khoản cố tình sai mật khẩu. Đây là kịch bản Discord bot phục vụ 1000 người trong một tiến trình; bản web thì mỗi sinh viên chạy riêng trên máy mình nên nhẹ hơn nhiều.

Kết quả nằm trong `tests/output/`:
- `loadtest_report.json`: số liệu và từng kiểm tra PASS/FAIL
- `loadtest_accounts.log`: log của từng tài khoản giả
- `loadtest_timeline.csv`: số luồng, RAM, CPU, hàng đợi của cổng giả theo từng giây

Tùy chọn hữu ích: `--turbo-share 1.0` (mọi người cùng bật Turbo), `--workers 30 --max-queue 300` (cổng trường yếu hơn), `--accounts 50 --open-after 12 --run-after-open 10` (chạy thử nhanh).
