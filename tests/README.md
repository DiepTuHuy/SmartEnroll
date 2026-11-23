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

## Xác suất vào được khi 1000 sinh viên khác đang chen (khoảng 15 phút)

```bash
venv/bin/python tests/login_chance.py --trials 20
```

Đây là bài trả lời câu hỏi chính: **1000 sinh viên khác (dùng trình duyệt, không dùng tool) đang chen vào cổng trường; tài khoản của tôi dùng SmartEnroll đăng nhập giữa lúc đông nhất thì có vào được không, và giành được lớp khó nhất với xác suất bao nhiêu %?**

Mỗi lần thử:
- cổng trường giả **yếu**: chỉ xử lý 8 request cùng lúc (chỉnh để mức nghẽn giống đợt đăng ký thật); thời gian xử lý mỗi request lấy theo số đo trên cổng thật lúc vắng
- 1000 sinh viên (`crowd.py`) ồ ạt đăng nhập trong 20 giây đầu, chờ lâu thì bấm lại, F5 trang đăng ký (gọi đúng các API trang thật gọi), tới giờ thì chọn môn → xem danh sách lớp → bấm vào lớp → bấm ĐĂNG KÝ liên tục, lớp đầy thì một nửa đổi lớp
- ở giây thứ 8, giữa lúc đông nhất, **4 tài khoản cùng bắt đầu và cùng nhắm 2 lớp bị tranh nhiều nhất** (khoảng 230 người giành 30 chỗ):
  - `tool-normal`, `tool-turbo`: SmartEnroll bản mới, chạy **đúng code `core_state.py`** (`my_tool.py`)
  - `human`: một sinh viên bình thường
  - `oldtool`: SmartEnroll bản cũ, mô phỏng theo đúng các timeout của bản cũ
- mở đăng ký ở giây thứ 40, kết thúc ở giây thứ 100

Hai kiểu cổng trường quá tải:
- `A_tu_choi_nhanh`: hàng chờ đầy là trả 503 ngay
- `B_xep_hang_lau`: bắt xếp hàng, chờ quá 60 giây thì 504 (giống lỗi timeout thật)

Hành vi của người thật là giả định (xem đầu file `crowd.py`); cổng giả cũng không phải cổng thật. Con số % chỉ đúng với cổng giả này, dùng để **so sánh** các cách vào, không phải lời hứa cho cổng trường thật.

## Cổng giả giống cổng thật tới đâu

Đã vào xem cổng thật (11/2026) bằng trình duyệt, **chỉ xem, không đăng ký / hủy / gửi gì**, rồi làm lại trong `fake_portal_server.py`:

| Quan sát trên cổng thật | Trong cổng giả |
|---|---|
| nginx đứng trước backend kiểu Spring, HTTP/2 | header `server: nginx`, `cache-control: no-store` |
| mọi API trả `{success, status, message, body, token, timestamp}`; đăng nhập trả token ở trường `token` | y như vậy |
| **mỗi tài khoản chỉ 1 phiên**: đăng nhập ở nơi khác thì token cũ bị 401 ngay | đăng nhập mới đá token cũ (`--multi-session` để tắt) |
| đăng nhập và đăng ký gửi kèm `?g-recaptcha-response=` | nhận tham số này, không kiểm tra |
| trang Đăng ký gọi `getDot` → `getLHPDaDangKy` + `getHocPhanHocMoi` → `getLopHocPhanChoDangKy` → `getLopHocPhanDetail` → `dangKyLopHocPhan` | đủ các API đó, đám đông gọi đúng trình tự đó |
| danh sách lớp không có sĩ số, chỉ có `phanTramDangKy`, `choDangKy`, `isCanhBao`, `tenTrangThai` | y như vậy, % tính từ số chỗ còn |
| lúc vắng: đăng nhập ~0,27 s, các trang 0,15–0,35 s, danh sách lớp ~0,45 s | dùng làm thời gian xử lý mỗi request |

Phần **giả định** (không xem được nếu không đăng ký, hoặc phải đợi giờ cao điểm): năng lực của cổng (số request xử lý cùng lúc, độ dài hàng chờ, thời gian chờ của nginx); request bị nginx trả 504 vẫn được backend xử lý sau đó (`--no-zombies` để tắt). Một lần đăng nhập "ma" như vậy vẫn cấp token, nên nó đá phiên đang dùng. Ngoài ra còn nội dung lỗi 401 và các câu thông báo khi đăng ký.

Hệ quả của "mỗi tài khoản 1 phiên": **trong giờ đăng ký đừng đăng nhập cùng tài khoản trên điện thoại / trình duyệt / bot khác**. Mỗi lần như vậy là tool bị đá ra và phải đăng nhập lại đúng lúc cổng nghẽn nhất. Nếu hai bản SmartEnroll (web và Discord) cùng chạy một tài khoản, chúng sẽ đá nhau liên tục.
