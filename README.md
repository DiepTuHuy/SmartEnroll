# 🎓 SmartEnroll UTH - Hệ thống Đăng ký Học phần Tự động

**SmartEnroll UTH** là một giải pháp tự động hóa đăng ký học phần hiện đại dành cho sinh viên trường Đại học Giao thông Vận tải TP.HCM (UTH). Hệ thống đã được nâng cấp toàn diện từ giao diện Tkinter cũ sang kiến trúc **Client-Server hiện đại** với giao diện web React JS cao cấp mang phong cách Glassmorphic, cùng với cơ chế tự động hóa đăng nhập và tìm kiếm đợt học kỳ (`idDot`) hoàn toàn qua API không cần click chuột.

---

## ✨ Điểm nổi bật & Tính năng chính

### 1. Trình tự động hóa Đăng nhập & Lấy Token siêu tốc (`auto_config.py`)
- **Tự động bắt gói tin (DevTools Log Listener):** Lắng nghe luồng HTTP requests của Chrome để bắt chính xác Bearer Token ngay khi đăng nhập.
- **Trích xuất LocalStorage qua JS:** Quét bộ nhớ trình duyệt để trích xuất Token dự phòng.
- **Tự động chuyển hướng:** Tự động điều hướng từ `/dashboard` sang trang đăng ký học phần `/coursesregistration` ngay sau khi đăng nhập thành công.
- **Tự động dò đợt học kì (`idDot` API):** Gọi trực tiếp API ẩn `https://portal.ut.edu.vn/api/v1/dkhp/getDot` của nhà trường để tải về danh sách các đợt đăng ký, tự động ưu tiên chọn đợt học kỳ đang hoạt động (`isDangKyHocPhan: true`) mà **không cần người dùng phải bấm chọn học kỳ thủ công**.
- **Tự đóng trình duyệt:** Tự động tắt trình duyệt Chrome và lưu cấu hình vào `config.json` chỉ sau 2 giây.

### 2. Giao diện Người dùng Premium (React JS Frontend)
- **Thiết kế Glassmorphism đẳng cấp:** Giao diện tối màu với hiệu ứng mờ kính cường lực, ánh sáng viền động (cyan & purple) tạo cảm giác cực kỳ công nghệ.
- **Micro-animations mượt mà:** Sử dụng thư viện `Framer Motion` tạo hiệu ứng xuất hiện, chuyển tab và cập nhật danh sách lớp học phần trơn tru.
- **Hộp tìm kiếm thông minh:** Dropdown tìm kiếm môn học tự động hoàn thành (Search Autocomplete) giúp tìm nhanh lớp học phần trong hàng trăm môn.
- **Terminal Console Thời gian thực:** Khung hiển thị log hoạt động dạng dòng lệnh chuyên nghiệp, tự động cuộn và tô màu thông minh (Thành công = Xanh lá, Cảnh báo = Vàng, Lỗi = Đỏ).
- **Thanh đo năng lực lớp học:** Cột hiển thị % số lượng sinh viên đã đăng ký trong lớp trực quan, tự động cảnh báo lớp đã đầy (FULL) hoặc bị khóa.
- **Bộ lọc bảo vệ lịch học:** Ngăn chặn việc tích chọn nhiều lớp của cùng một môn để tránh xung đột thời khóa biểu.

### 3. Máy chủ Proxy & Spam Controller (Flask Backend)
- **Bypass CORS:** Hoạt động như một Reverse Proxy trên cổng `5001` giúp chuyển tiếp các yêu cầu đăng ký lên máy chủ UTH mà không bị chặn bởi CORS của trình duyệt.
- **Đa luồng hiệu năng cao (Multithreading):** Chạy luồng spam gửi yêu cầu đăng ký riêng biệt để không làm đơ giao diện điều khiển.
- **Tự động quản lý vòng lặp (Smart Retry):** Gửi yêu cầu đăng ký liên tục (khoảng cách 0.5s để tránh nghẽn IP/bị chặn cổng) đối với các lớp chưa thành công cho đến khi đăng ký thành công hoặc có lệnh dừng.

---

## 🛠 Kiến trúc Hệ thống

- **Frontend:** React JS (Vite), Framer Motion, Vanilla CSS (Custom CSS Variables).
- **Backend:** Python (Flask, Flask-CORS, Requests).
- **Driver:** Undetected Chromedriver (Selenium), Chrome DevTools Protocol logs listener.

---

## 🚀 Hướng dẫn Cài đặt & Chạy Hệ thống

### 1. Yêu cầu Hệ thống
Để vận hành hệ thống, máy tính của bạn cần được cài đặt sẵn:
- **Python** (Bản 3.8 trở lên)
- **Node.js** (Bản 16 trở lên, đã bao gồm `npm`)
- **Google Chrome** (Trình duyệt chính thức bản mới nhất)

### 2. Cài đặt các thư viện liên quan
Mở Terminal tại thư mục gốc của dự án `SmartEnroll` và chạy lệnh cài đặt thư viện cho cả Backend và Frontend:

```bash
# Cài đặt thư viện Python cho Backend
pip install -r requirements.txt
```

*(Đối với React Frontend, hệ thống sẽ tự động cài đặt thư viện `node_modules` thông qua `npm install` trong lần chạy đầu tiên).*

### 3. Khởi động toàn bộ Hệ thống
Chạy lệnh duy nhất sau ở thư mục gốc:

```bash
python start.py
```

Sau khi chạy lệnh, hệ thống sẽ tự động:
1. Giải phóng các tiến trình chiếm dụng cổng `5001`.
2. Khởi chạy Flask API Server trên cổng `5001`.
3. Kiểm tra và cài đặt thư viện frontend (nếu chưa có).
4. Khởi chạy React Web Client trên cổng `5173`.
5. Tự động mở trình duyệt mặc định của bạn truy cập địa chỉ: **[http://localhost:5173](http://localhost:5173)**.

---

## 📖 Hướng dẫn sử dụng Hệ thống

### Bước 1: Cấu hình tự động lấy Token
1. Trên giao diện Web SmartEnroll, chuyển sang tab **Cấu hình** (Configuration).
2. Nhấn nút **BẮT ĐẦU QUÉT TỰ ĐỘNG (AUTO CONFIG)**.
3. Một cửa sổ Google Chrome sạch sẽ xuất hiện. Bạn chỉ cần nhập tài khoản, mật khẩu UTH và tiến hành đăng nhập bình thường.
4. Ngay khi đăng nhập thành công, Chrome sẽ tự động đóng lại. Giao diện Web của bạn sẽ cập nhật trạng thái `ĐÃ CÓ CẤU HÌNH` kèm theo Token và ID Đợt học kỳ mới nhất (`76`, `77`...) vừa tự động quét được.

### Bước 2: Tìm kiếm lớp học phần
1. Quay lại tab **Bảng điều khiển** (Dashboard).
2. Nhấp vào thanh chọn môn học, gõ từ khóa tên môn hoặc mã học phần (ví dụ: *Giải tích*, *Lập trình*) để tìm kiếm môn học nhanh.
3. Chọn môn học cần đăng ký và bấm nút **🔎 QUÉT CHI TIẾT LỚP HỌC**.
4. Danh sách các lớp học phần đang mở kèm thông tin lịch học, phòng học, giảng viên và sĩ số hiện tại sẽ hiện ra trực quan.

### Bước 3: Thiết lập danh sách chờ & Chạy Auto
1. Tích chọn vào ô đầu dòng của lớp học phần bạn muốn đăng ký.
2. Các lớp được chọn sẽ tự động chuyển vào danh sách chờ ở bảng bên phải.
3. Khi đã chọn xong tất cả các môn cần thiết, bấm nút **🚀 CHẠY SPAM ĐĂNG KÝ**.
4. Hệ thống sẽ bắt đầu gửi yêu cầu liên tục lên máy chủ trường. Bạn có thể theo dõi tiến độ thời gian thực trực tiếp tại khung **Bảng Log Hoạt động** nằm ở phía dưới giao diện.
5. Khi muốn kết thúc hoặc thay đổi danh sách lớp, bấm nút **⏹ DỪNG SPAM**.

---

## 🔍 Khắc phục lỗi (Troubleshooting)

- **Tự động nhận diện phiên bản Chrome:**
  - Hệ thống hiện nay đã tự động tìm kiếm và phát hiện phiên bản Chrome đang được cài đặt trên hệ điều hành của bạn (Windows & macOS) để cấu hình cho Selenium. Lỗi lệch phiên bản (Chrome Version Mismatch) đã được tự động giải quyết triệt để.
- **Lỗi Cổng 5001 bị chiếm dụng:**
  - Trên hệ điều hành macOS, tính năng *AirPlay Receiver* có thể chiếm dụng cổng `5000` hoặc `5001`. Script `start.py` đã tự động tìm giải phóng, tuy nhiên nếu vẫn bị đụng độ cổng, hãy tắt tính năng *AirPlay Receiver* trong mục Cài đặt hệ thống (System Settings) của macOS.
- **Lỗi Token hết hạn (HTTP 401):**
  - Máy chủ trường sẽ hủy phiên đăng nhập (Token) của sinh viên sau khoảng 15-30 phút không tương tác. Nếu bảng log thông báo `💀 Token hết hạn!`, bạn chỉ cần chuyển sang tab **Cấu hình** và bấm **Bắt đầu quét tự động** để lấy lại Token mới một cách dễ dàng.

---

Chúc các bạn sinh viên UTH có một kỳ đăng ký học phần thành công rực rỡ! 🎓🎉
