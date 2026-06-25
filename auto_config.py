import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import json
import time
import os
import ssl

# Fix SSL certificate verification issue
ssl._create_default_https_context = ssl._create_unverified_context

CONFIG_FILE = "config.json"

def get_chrome_major_version():
    import platform
    import os
    import re
    import subprocess
    
    system = platform.system()
    if system == "Darwin": # macOS
        paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Google Chrome.app/Contents/Info.plist"
        ]
        for path in paths:
            if os.path.exists(path):
                if path.endswith("Info.plist"):
                    try:
                        import plistlib
                        with open(path, "rb") as f:
                            plist = plistlib.load(f)
                            version = plist.get("CFBundleShortVersionString")
                            if version:
                                return int(version.split(".")[0])
                    except Exception:
                        pass
                else:
                    try:
                        out = subprocess.check_output([path, "--version"]).decode("utf-8")
                        match = re.search(r"Google Chrome (\d+)", out)
                        if match:
                            return int(match.group(1))
                    except Exception:
                        pass
    elif system == "Windows":
        try:
            import winreg
            keys = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Google Chrome"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Google Chrome")
            ]
            for hkey, path in keys:
                try:
                    with winreg.OpenKey(hkey, path) as key:
                        val, _ = winreg.QueryValueEx(key, "") if "App Paths" in path else winreg.QueryValueEx(key, "DisplayVersion")
                        if val:
                            if os.path.exists(val):
                                dir_path = os.path.dirname(val)
                                for item in os.listdir(dir_path):
                                    if item[0].isdigit() and os.path.isdir(os.path.join(dir_path, item)):
                                        return int(item.split(".")[0])
                            else:
                                return int(val.split(".")[0])
                except Exception:
                    pass
        except Exception:
            pass
            
        win_paths = [
            os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Google\\Chrome\\Application"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Google\\Chrome\\Application"),
            os.path.join(os.environ.get("LocalAppData", ""), "Google\\Chrome\\Application")
        ]
        for p in win_paths:
            if os.path.exists(p):
                for item in os.listdir(p):
                    if item[0].isdigit() and os.path.isdir(os.path.join(p, item)):
                        return int(item.split(".")[0])
    return None

def fetch_latest_id_dot(token, cookie):
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    headers = {
        "Authorization": token if "Bearer" in token else f"Bearer {token}",
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    endpoints = [
        "https://portal.ut.edu.vn/api/v1/dkhp/getDot",
        "https://portal.ut.edu.vn/api/v1/dkhp/getDotDangKy",
        "https://portal.ut.edu.vn/api/v1/dkhp/getDotDangKyHocPhan",
        "https://portal.ut.edu.vn/api/v1/dkhp/getDotDangKyChoSinhVien",
        "https://portal.ut.edu.vn/api/v1/dkhp/getDotDangKyHocPhanChoSinhVien",
        "https://portal.ut.edu.vn/api/v1/dkhp/getDotHoc",
        "https://portal.ut.edu.vn/api/v1/dkhp/getDotHocPhan"
    ]
    
    for url in endpoints:
        try:
            resp = requests.get(url, headers=headers, timeout=4, verify=False)
            if resp.status_code == 200:
                res_json = resp.json()
                dots = res_json.get("data") or res_json.get("body")
                if dots and isinstance(dots, list):
                    valid_dots = []
                    for dot in dots:
                        dot_id = dot.get('id') or dot.get('idDot') or dot.get('maDot') or dot.get('idDotDangKy')
                        if dot_id is not None:
                            is_active = dot.get('isDangKyHocPhan') or dot.get('dangKyHocPhan') or False
                            valid_dots.append((str(dot_id), is_active, dot))
                    
                    if valid_dots:
                        try:
                            # Prioritize isDangKyHocPhan = True, then sort by ID descending
                            valid_dots.sort(key=lambda x: (1 if x[1] else 0, int(x[0]) if x[0].isdigit() else 0), reverse=True)
                        except:
                            valid_dots.sort(key=lambda x: (1 if x[1] else 0, x[0]), reverse=True)
                            
                        latest_id, is_act, latest_dot = valid_dots[0]
                        name_key = latest_dot.get('tenHocKy') or latest_dot.get('tenDot') or latest_dot.get('tenDotDangKy') or ''
                        print(f"🎉 TÌM THẤY ĐỢT ĐĂNG KÝ: ID {latest_id} ({name_key}) - Active: {is_act}")
                        return latest_id
        except Exception:
            pass
    return None

def get_auto_config():
    print("🚀 Đang khởi động 'Điệp viên' Chrome...")
    
    options = uc.ChromeOptions()
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'}) 
    
    try:
        # Tự động phát hiện phiên bản Chrome
        chrome_version = get_chrome_major_version()
        if chrome_version:
            print(f"🖥️ Phát hiện phiên bản Chrome cài đặt: {chrome_version}")
            driver = uc.Chrome(options=options, version_main=chrome_version, use_subprocess=True)
        else:
            print("⚠️ Không thể tự động phát hiện phiên bản Chrome, sử dụng cấu hình mặc định của undetected-chromedriver...")
            driver = uc.Chrome(options=options, use_subprocess=True)
        driver.set_window_size(1000, 800)
        
        # 2. Vào trang Dashboard
        print("🌍 Đang truy cập Portal...")
        driver.get("https://portal.ut.edu.vn/")
        
        print("👉 VUI LÒNG ĐĂNG NHẬP BẰNG TAY TRONG CỬA SỔ CHROME!")
        print("💡 GỢI Ý: Sau khi đăng nhập, hãy bấm vào menu 'Đăng ký học phần' để hệ thống tự động bắt được Đợt đăng ký!")
        print("⏳ Tool đang âm thầm quét gói tin để tìm Token và ID Đợt...")

        found_token = None
        found_cookie = None
        found_id_dot = None
        has_redirected = False

        # 3. Vòng lặp quét mạng (Network Sniffing)
        for i in range(120): # Chờ tối đa 2 phút
            
            # Lấy nhật ký mạng từ Chrome
            logs = []
            try:
                if not driver.window_handles:
                    print("❌ Trình duyệt đã bị đóng.")
                    break
                logs = driver.get_log('performance') 
            except Exception as e:
                print(f"⚠️ Cảnh báo kết nối DevTools (tạm thời): {e}")
                try:
                    if not driver.window_handles:
                        print("❌ Trình duyệt đã bị đóng.")
                        break
                except:
                    break
                time.sleep(1)
                continue

            for entry in logs:
                try:
                    obj = json.loads(entry['message'])
                    message = obj.get('message', {})
                    method = message.get('method')
                    
                    if method == 'Network.requestWillBeSent':
                        params = message.get('params', {})
                        request = params.get('request', {})
                        url = request.get('url', '')
                        headers = request.get('headers', {})
                        
                        # --- TÌM TOKEN (Authorization) ---
                        auth = headers.get('Authorization') or headers.get('authorization')
                        if auth and "Bearer" in auth:
                            if len(auth) > 20:
                                found_token = auth
                                print(f"🔥 BẮT ĐƯỢC TOKEN RỒI: {auth[:25]}...")
                        
                        # --- TÌM ID ĐỢT ĐĂNG KÝ TỰ ĐỘNG (Từ query string) ---
                        import urllib.parse
                        parsed_url = urllib.parse.urlparse(url)
                        query_params = urllib.parse.parse_qs(parsed_url.query)
                        
                        for key, values in query_params.items():
                            if 'dot' in key.lower() and ('id' in key.lower() or 'dangky' in key.lower()):
                                if values and values[0].isdigit():
                                    found_id_dot = values[0]
                                    print(f"🔥 BẮT ĐƯỢC ID ĐỢT ĐĂNG KÝ (GET): {found_id_dot}")
                        
                        # --- TÌM ID ĐỢT ĐĂNG KÝ TỰ ĐỘNG (Từ post data) ---
                        post_data = request.get('postData', '')
                        if post_data:
                            try:
                                post_json = json.loads(post_data)
                                for k, v in post_json.items():
                                    if 'dot' in k.lower() and 'id' in k.lower():
                                        if str(v).isdigit():
                                            found_id_dot = str(v)
                                            print(f"🔥 BẮT ĐƯỢC ID ĐỢT ĐĂNG KÝ (POST JSON): {found_id_dot}")
                            except:
                                for item in post_data.split('&'):
                                    if '=' in item:
                                        k, v = item.split('=', 1)
                                        if 'dot' in k.lower() and 'id' in k.lower():
                                            if v.isdigit():
                                                found_id_dot = v
                                                print(f"🔥 BẮT ĐƯỢC ID ĐỢT ĐĂNG KÝ (POST FORM): {found_id_dot}")

                except Exception:
                    pass
            
            # --- CỐ GẮNG TRÍCH XUẤT TOKEN QUA JAVASCRIPT ---
            if not found_token:
                try:
                    js_token_script = """
                    function findToken() {
                        const tokenKeys = ['token', 'accesstoken', 'access_token', 'jwt', 'auth', 'authorization', 'bearer', 'id_token', 'credential'];
                        for (let i = 0; i < localStorage.length; i++) {
                            let key = localStorage.key(i);
                            let val = localStorage.getItem(key);
                            if (val && typeof val === 'string') {
                                if (val.startsWith('Bearer ') || val.startsWith('bearer ') || val.includes('eyJ')) return val;
                                if (tokenKeys.some(k => key.toLowerCase().includes(k)) && val.length > 20) return val;
                                try {
                                    let obj = JSON.parse(val);
                                    for (let k in obj) {
                                        if (typeof obj[k] === 'string' && (obj[k].startsWith('Bearer ') || obj[k].includes('eyJ') || (tokenKeys.some(tk => k.toLowerCase().includes(tk)) && obj[k].length > 20))) return obj[k];
                                    }
                                } catch(e) {}
                            }
                        }
                        for (let i = 0; i < sessionStorage.length; i++) {
                            let key = sessionStorage.key(i);
                            let val = sessionStorage.getItem(key);
                            if (val && typeof val === 'string') {
                                if (val.startsWith('Bearer ') || val.startsWith('bearer ') || val.includes('eyJ')) return val;
                                if (tokenKeys.some(k => key.toLowerCase().includes(k)) && val.length > 20) return val;
                                try {
                                    let obj = JSON.parse(val);
                                    for (let k in obj) {
                                        if (typeof obj[k] === 'string' && (obj[k].startsWith('Bearer ') || obj[k].includes('eyJ') || (tokenKeys.some(tk => k.toLowerCase().includes(tk)) && obj[k].length > 20))) return obj[k];
                                    }
                                } catch(e) {}
                            }
                        }
                        return null;
                    }
                    return findToken();
                    """
                    js_token = driver.execute_script(js_token_script)
                    if js_token:
                        clean_token = js_token if "Bearer" in js_token else f"Bearer {js_token}"
                        if len(clean_token) > 20:
                            found_token = clean_token
                            print(f"🔥 BẮT ĐƯỢC TOKEN QUA JS: {found_token[:30]}...")
                except Exception:
                    pass

            try:
                current_url = driver.current_url
                cookies_list = driver.get_cookies()
                current_cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies_list])
            except Exception:
                current_url = ""
                current_cookie_str = ""

            # --- TỰ ĐỘNG CHUYỂN HƯỚNG SANG TRANG ĐĂNG KÝ KHI ĐÃ ĐĂNG NHẬP ---
            if "/dashboard" in current_url and not has_redirected:
                print("🔄 Phát hiện đã đăng nhập thành công! Tự động chuyển hướng sang trang đăng ký...")
                has_redirected = True
                try:
                    driver.get("https://portal.ut.edu.vn/coursesregistration")
                except Exception:
                    pass
            
            # --- TỰ ĐỘNG TRUY VẤN LẤY ID ĐỢT KHI ĐÃ CÓ TOKEN VÀ COOKIE ---
            if found_token and not found_id_dot and current_cookie_str:
                print("📡 Đang truy vấn API trường để tự động lấy đợt đăng ký mới nhất...")
                found_id_dot = fetch_latest_id_dot(found_token, current_cookie_str)
                if not found_id_dot:
                    print("⚠️ Chưa truy vấn được đợt đăng ký qua API. Chờ trình duyệt tự tải...")
            
            # Điều kiện thoát: Tìm thấy cả Token Bearer và idDot
            if found_token and found_id_dot:
                found_cookie = current_cookie_str
                break
            
            # Mẹo: Refresh trang nếu đã đăng nhập nhưng chưa bắt được token
            if "ASP.NET" in current_cookie_str and not found_token and i == 20:
                print("🔄 Đang thử tải lại trang để bắt Token...")
                try:
                    driver.refresh()
                except Exception:
                    pass

            if i % 5 == 0:
                print(f"🕵️ Đang rà soát... (Giây thứ {i})")
            
            time.sleep(1)

        # 4. Kết thúc & Lưu file
        try:
            driver.quit()
        except:
            pass
        
        if found_token:
            print("\n✅ THÀNH CÔNG MỸ MÃN!")
            
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            
            # Đọc config cũ nếu có
            old_config = {}
            if os.path.exists(CONFIG_FILE):
                try:
                    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                        old_config = json.load(f)
                except:
                    pass
            
            # Ưu tiên id_dot mới bắt được, nếu không có thì giữ lại cái cũ, cuối cùng mới mặc định là "75"
            final_id_dot = found_id_dot or old_config.get("id_dot") or "75"
            
            config_data = {
                "api_url": "https://portal.ut.edu.vn/coursesregistration",
                "token": found_token.replace("Bearer ", "").strip(),
                "cookie": current_cookie_str if current_cookie_str else old_config.get("cookie", ""),
                "id_dot": final_id_dot,
                "user_agent": user_agent
            }
            
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)
                
            print(f"📂 Đã lưu cấu hình vào file {CONFIG_FILE}.")
            return config_data
        else:
            print("\n❌ Thất bại! Không tìm thấy Token.")
            return None

    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return None

if __name__ == "__main__":
    get_auto_config()
