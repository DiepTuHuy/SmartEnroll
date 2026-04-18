import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import json
import time
import os
import ssl

# Fix SSL certificate verification issue
ssl._create_default_https_context = ssl._create_unverified_context

CONFIG_FILE = "config.json"
CHROME_VERSION = 147  # Cập nhật phiên bản Chrome

def get_auto_config():
    print("🚀 Đang khởi động 'Điệp viên' Chrome...")
    
    options = uc.ChromeOptions()
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'}) 
    
    try:
        # Khởi tạo Chrome
        driver = uc.Chrome(options=options, version_main=CHROME_VERSION, use_subprocess=True)
        driver.set_window_size(1000, 800)
        
        # 2. Vào trang Dashboard
        print("🌍 Đang truy cập Portal...")
        driver.get("https://portal.ut.edu.vn/")
        
        print("👉 VUI LÒNG ĐĂNG NHẬP BẰNG TAY TRONG CỬA SỔ CHROME!")
        print("⏳ Tool đang âm thầm quét gói tin để tìm Token...")

        found_token = None
        found_cookie = None
        id_dot = "75" # Mặc định

        # 3. Vòng lặp quét mạng (Network Sniffing)
        # Tool sẽ đọc liên tục các gói tin Chrome gửi đi
        for i in range(120): # Chờ tối đa 2 phút
            
            # Lấy nhật ký mạng từ Chrome
            try:
                logs = driver.get_log('performance') 
            except:
                continue

            for entry in logs:
                try:
                    obj = json.loads(entry['message'])
                    message = obj.get('message', {})
                    method = message.get('method')
                    
                    # Chỉ quan tâm đến các Gói tin Gửi đi (Request)
                    if method == 'Network.requestWillBeSent':
                        params = message.get('params', {})
                        request = params.get('request', {})
                        headers = request.get('headers', {})
                        
                        # --- TÌM TOKEN (Authorization) ---
                        # Token có thể viết hoa hoặc thường tùy gói tin
                        auth = headers.get('Authorization') or headers.get('authorization')
                        
                        if auth and "Bearer" in auth:
                            # Tìm thấy Token xịn!
                            if len(auth) > 20: # Lọc token rác
                                found_token = auth
                                print(f"\n🔥 BẮT ĐƯỢC TOKEN RỒI: {auth[:20]}...")
                        
                        # --- TÌM ID ĐỢT (Nếu lỡ bắt được gói tin đăng ký) ---
                        # Nếu web gọi API dotDangKy, ta lấy luôn ID
                        if "dotDangKy" in request.get('url', ''):
                            # (Logic phức tạp hơn cần parse response, tạm thời bỏ qua)
                            pass

                except Exception:
                    pass
            
            # Lấy Cookie (Dễ hơn, lấy trực tiếp từ trình duyệt)
            cookies_list = driver.get_cookies()
            current_cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies_list])
            
            # Điều kiện thoát: Tìm thấy Token Bearer
            if found_token:
                found_cookie = current_cookie_str
                break
            
            # Mẹo: Nếu người dùng đã đăng nhập xong (có cookie xịn) mà chưa thấy Token
            # Ta thử Refresh trang để Web buộc phải gửi lại Token
            if "ASP.NET" in current_cookie_str and i == 20:
                print("🔄 Đang thử tải lại trang để bắt Token...")
                driver.refresh()

            if i % 5 == 0:
                print(f"🕵️ Đang rà soát... ({i}s)")
            
            time.sleep(1)

        # 4. Kết thúc & Lưu file
        driver.quit()
        
        if found_token:
            print("\n✅ THÀNH CÔNG MỸ MÃN!")
            
            # Lưu user agent
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            
            config_data = {
                "api_url": "https://portal.ut.edu.vn/coursesregistration", # URL thật
                "token": found_token.replace("Bearer ", "").strip(), # Chỉ lấy phần mã
                "cookie": found_cookie,
                "id_dot": id_dot,
                "user_agent": user_agent
            }
            
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)
                
            print(f"📂 Đã lưu vào file {CONFIG_FILE}. Bạn có thể chạy Tool Spam ngay!")
            return config_data
        else:
            print("\n❌ Hết giờ! Không bắt được gói tin nào chứa Token.")
            print("💡 Gợi ý: Sau khi đăng nhập, hãy bấm thử vào menu 'Đăng ký học phần' để web gửi gói tin đi.")
            return None

    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return None

if __name__ == "__main__":
    get_auto_config()
