# UTH Auto Course Registration (Auto ĐKHP)

Đây là công cụ hỗ trợ đăng ký học phần tự động (Auto ĐKHP) dành cho sinh viên UTH. Tool giúp tự động lấy Token đăng nhập mà không cần thao tác F12 phức tạp và hỗ trợ Spam đăng ký liên tục để tăng tỉ lệ thành công vào các lớp đã đầy.

## Bắt đầu (Getting Started)

Để cài đặt và chạy tool trên máy tính cá nhân, bạn hãy làm theo các bước đơn giản dưới đây.

### Yêu cầu tiên quyết (Prerequisites)

Dưới đây là các phần mềm bạn cần có trước khi cài đặt tool:

* **Python (Bản 3.8 trở lên)**:
    Nếu chưa có, tải tại [python.org](https://www.python.org/downloads/). Khi cài nhớ tích vào ô *Add Python to PATH*.
    
* **Google Chrome**:
    Đảm bảo bạn đang sử dụng trình duyệt Chrome mới nhất.
    * *Lưu ý:* Kiểm tra phiên bản Chrome của bạn (Vào `Cài đặt` -> `Giới thiệu về Chrome`).
    * Mở file `auto_config.py` và sửa dòng `CHROME_VERSION = 144` thành số phiên bản của bạn (Ví dụ: 120, 121...).

### Cài đặt (Installation)

Dưới đây là hướng dẫn chi tiết cách tải và thiết lập môi trường.

1.  **Clone repository về máy** (hoặc tải file Zip và giải nén)
    ```sh
    git clone https://github.com/DiepTuHuy/SmartEnroll.git
    ```

2.  **Cài đặt các thư viện cần thiết**
    Mở Terminal (hoặc CMD/PowerShell) tại thư mục vừa tải về và chạy lệnh sau:
    ```sh
    pip install -r requirements.txt
    ```

3.  **Cấu hình Token tự động**
    Thay vì phải lấy cookie thủ công, hãy chạy script sau để tool tự động "bắt" Token từ trình duyệt:
    ```sh
    python auto_config.py
    ```
    * Một cửa sổ Chrome sẽ hiện lên -> Bạn đăng nhập vào Portal.
    * Sau khi đăng nhập thành công, Chrome sẽ tự tắt.
    * Khi tool báo `✅ THÀNH CÔNG MỸ MÃN!`, file `config.json` sẽ tự động được tạo.

## Hướng dẫn sử dụng (Usage)

Sau khi đã có file `config.json` từ bước trên, bạn tiến hành chạy tool chính.

1.  **Khởi động Tool**
    ```sh
    python main.py
    ```

2.  **Thao tác trên giao diện:**
    * **Bước 1:** Tại mục *Tìm kiếm lớp*, chọn Môn học bạn muốn đăng ký.
    * **Bước 2:** Bấm nút `🔎 QUÉT CHI TIẾT`. Danh sách lớp sẽ hiện ra bên dưới.
    * **Bước 3:** Tích chọn (☑) vào các lớp bạn muốn Spam (có thể chọn nhiều lớp cùng lúc).
    * **Bước 4:** Bấm `🚀 CHẠY SPAM` và treo máy để tool tự làm việc.

## Sửa lỗi thường gặp (Troubleshooting)

* **Lỗi "Thiếu config.json"**:
    * Bạn chưa chạy `auto_config.py` hoặc chạy chưa thành công. Hãy làm lại bước Cài đặt số 3.
    
* **Lỗi HTTP 401 (Token hết hạn)**:
    * Token của trường thường hết hạn sau 15-30 phút. Nếu đang chạy mà thấy lỗi này, hãy tắt tool và chạy lại `auto_config.py` để lấy Token mới.

* **Lỗi Chrome version mismatch**:
    * Vào file `auto_config.py`, sửa dòng `CHROME_VERSION` cho khớp với phiên bản Chrome hiện tại trên máy bạn.

## Liên hệ

Nếu gặp lỗi trong quá trình sử dụng, vui lòng tạo Issue trên Github hoặc liên hệ trực tiếp.

Link Project: [https://github.com/DiepTuHuy/SmartEnroll](https://github.com/DiepTuHuy/SmartEnroll)

<p align="right">(<a href="#top">back to top</a>)</p>
