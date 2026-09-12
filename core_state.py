import os
import json
import threading
import time
import requests
import random
import string
import concurrent.futures
from auto_config import get_auto_config

# MAPPING CÁC CA HỌC
CA_HOC = {
    "Ca 1 (Tiết 1-3)":   [1, 2, 3],
    "Ca 2 (Tiết 4-6)":   [4, 5, 6],
    "Ca 3 (Tiết 7-9)":   [7, 8, 9],
    "Ca 4 (Tiết 10-12)": [10, 11, 12],
    "Ca 5 (Tiết 13-15)": [13, 14, 15]
}

_app_states = {}

def get_app_state(user_id="default"):
    if user_id not in _app_states:
        _app_states[user_id] = AppState(user_id)
    return _app_states[user_id]

class AppState:
    def __init__(self, user_id="default"):
        self.user_id = str(user_id)
        # Lưu config theo từng user_id
        if self.user_id == "default":
            self.config_file = os.path.join(os.path.expanduser("~"), ".smartenroll_config.json")
        else:
            self.config_file = os.path.join(os.path.expanduser("~"), f".smartenroll_config_{self.user_id}.json")
            
        self.is_spamming = False
        self.spam_thread = None
        self.logs = []
        self.stats = {
            "total_requests": 0,
            "success_count": 0,
            "error_count": 0
        }
        self.is_auto_configuring = False
        self.auto_config_thread = None
        self.auto_config_status = "idle"
        self.last_login_error = ""
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=200, max_retries=1)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.config = None
        self.load_config_data()
        
        self.registered_classes_schedules = {}
        threading.Thread(target=self.run_token_refresher_loop, daemon=True).start()

    def load_config_data(self):
        if not os.path.exists(self.config_file) and os.path.exists("config.json"):
            try:
                import shutil
                shutil.copy("config.json", self.config_file)
                self.log(f"Đã tự động di chuyển config.json sang {self.config_file}")
            except Exception as e:
                self.log(f"Lỗi khi di chuyển config.json: {e}")

        if not hasattr(self, '_token_cache'):
            self._token_cache = None
        if not hasattr(self, '_cookie_cache'):
            self._cookie_cache = None
        if not hasattr(self, '_ua_cache'):
            self._ua_cache = None

        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
                    
                    if self.config.get('token'):
                        self._token_cache = self.config.get('token')
                    if self.config.get('cookie'):
                        self._cookie_cache = self.config.get('cookie')
                    if self.config.get('user_agent'):
                        self._ua_cache = self.config.get('user_agent')
                        
                    if not self.config.get('token') and self._token_cache:
                        self.config['token'] = self._token_cache
                    if not self.config.get('cookie') and self._cookie_cache:
                        self.config['cookie'] = self._cookie_cache
                    if not self.config.get('user_agent') and self._ua_cache:
                        self.config['user_agent'] = self._ua_cache
                        
                    self.update_session_headers()
                    
                if self.config and self.config.get("username") and self.config.get("password"):
                    try:
                        test_resp = self.session.get("https://portal.ut.edu.vn/api/v1/dkhp/getDot", timeout=3, verify=False)
                        if test_resp.status_code == 401:
                            self.log("🔄 Phát hiện token cũ đã hết hạn. Đang tự động đăng nhập lại...")
                            self.login_with_credentials(self.config["username"], self.config["password"])
                    except Exception as e:
                        pass
                return True
            except Exception as e:
                self.log(f"Lỗi đọc config.json: {e}")
        self.config = None
        return False

    def run_token_refresher_loop(self):
        while True:
            time.sleep(600)
            if self.config and self.config.get("username") and self.config.get("password"):
                self.log("🔄 [Auto-Refresher] Đang tiến hành gia hạn tự động token cổng trường định kỳ (10 phút)...")
                try:
                    success = self.login_with_credentials(self.config["username"], self.config["password"])
                    if success:
                        self.log("✅ [Auto-Refresher] Tự động gia hạn token thành công!")
                    else:
                        self.log("❌ [Auto-Refresher] Tự động gia hạn token thất bại!")
                except Exception as e:
                    self.log(f"⚠️ [Auto-Refresher] Lỗi khi gia hạn token tự động: {e}")

    def update_session_headers(self):
        if self.config:
            self.session.headers.update({
                "Authorization": f"Bearer {self.config.get('token', '')}",
                "Cookie": self.config.get('cookie', ''),
                "User-Agent": self.config.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            })

    def login_with_credentials(self, username, password):
        fake_captcha = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))
        url = f"https://portal.ut.edu.vn/api/v1/user/login?g-recaptcha-response={fake_captcha}"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://portal.ut.edu.vn",
            "Referer": "https://portal.ut.edu.vn/login"
        }
        payload = {
            "username": username,
            "password": password
        }
        self.last_login_error = ""
        try:
            self.session.cookies.clear()
            self.session.headers.clear()
            resp = self.session.post(url, json=payload, headers=headers, timeout=10, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success") and data.get("token"):
                    token = data.get("token")
                    cookie_str = "; ".join([f"{k}={v}" for k, v in self.session.cookies.items()])
                    
                    dot_url = "https://portal.ut.edu.vn/api/v1/dkhp/getDot"
                    dot_headers = {
                        "Authorization": f"Bearer {token}",
                        "Cookie": cookie_str,
                        "User-Agent": headers["User-Agent"]
                    }
                    latest_dot = self.config.get("id_dot", "76") if self.config else "76"
                    try:
                        self.session.headers.update(dot_headers)
                        dot_resp = self.session.get(dot_url, timeout=5, verify=False)
                        if dot_resp.status_code == 200:
                            dot_data = dot_resp.json().get('data') or dot_resp.json().get('body') or []
                            if dot_data:
                                dot_ids = [str(d.get('id') or d.get('idDot')) for d in dot_data if d.get('id') or d.get('idDot')]
                                if dot_ids:
                                    latest_dot = dot_ids[0]
                                    self.log(f"📅 Tự động quét và cấu hình ID Đợt học mới nhất: {latest_dot}")
                    except Exception as e:
                        self.log(f"⚠️ Không thể tự động quét đợt học sau đăng nhập: {e}")

                    old_fb_user = self.config.get("fb_username", "") if self.config else ""
                    old_fb_pass = self.config.get("fb_password", "") if self.config else ""
                    
                    self.config = {
                        "api_url": "https://portal.ut.edu.vn/coursesregistration",
                        "token": token,
                        "cookie": cookie_str,
                        "id_dot": latest_dot,
                        "user_agent": headers["User-Agent"],
                        "username": username,
                        "password": password,
                        "fb_username": old_fb_user,
                        "fb_password": old_fb_pass
                    }
                    
                    self._token_cache = token
                    self._cookie_cache = cookie_str
                    
                    with open(self.config_file, "w", encoding="utf-8") as f:
                        json.dump(self.config, f, indent=4)
                    self.update_session_headers()
                    self.log(f"🔑 Đăng nhập thành công tài khoản: {username}!")
                    return True
                else:
                    self.last_login_error = data.get('message', 'Sai tài khoản hoặc mật khẩu!')
                    self.log(f"❌ Đăng nhập thất bại: {self.last_login_error}")
            else:
                self.last_login_error = f"Portal trả về mã {resp.status_code}"
                self.log(f"❌ Đăng nhập thất bại, mã lỗi: {resp.status_code}")
        except Exception as e:
            self.last_login_error = f"Không thể kết nối cổng trường: {e}"
            self.log(f"❌ Lỗi kết nối cổng trường: {e}")
        return False

    def request_with_retry(self, method, url, **kwargs):
        try:
            resp = self.session.request(method, url, **kwargs)
            if resp.status_code == 401:
                if self.config and self.config.get("username") and self.config.get("password"):
                    self.log("🔄 Token hết hạn (401). Đang tiến hành gia hạn tự động...")
                    if self.login_with_credentials(self.config["username"], self.config["password"]):
                        if "headers" in kwargs and "Authorization" in kwargs["headers"]:
                            kwargs["headers"]["Authorization"] = f"Bearer {self.config['token']}"
                        resp = self.session.request(method, url, **kwargs)
            return resp
        except Exception as e:
            raise e

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        self.logs.append(log_entry)
        if len(self.logs) > 300:
            self.logs.pop(0)

    def fetch_class_detail(self, class_id, is_conditional=False):
        if is_conditional:
            url = "https://portal.ut.edu.vn/api/v1/dkhpdk/getLopHocPhanDetail"
        else:
            url = "https://portal.ut.edu.vn/api/v1/dkhp/getLopHocPhanDetail"
        params = {"idLopHocPhan": class_id}
        for _ in range(3):
            try:
                resp = self.request_with_retry("GET", url, params=params, timeout=5)
                if resp.status_code == 200:
                    return resp.json().get('body') or []
                time.sleep(0.1)
            except Exception:
                pass
        return None

    def format_schedule(self, details):
        if not details:
            return "⚠️ Không lấy được lịch"
        parts = []
        for d in details:
            raw_thu = str(d.get('thu', ''))
            thu_text = "Chủ Nhật" if raw_thu in ['8', 'CN', 'Chủ Nhật'] else f"Thứ {raw_thu}"
            tiet = d.get('tietHoc', '?')
            phong = d.get('phong') or d.get('tenPhong') or ""
            phong_text = f" - P.{phong}" if phong else ""
            parts.append(f"{thu_text} (Tiết {tiet}){phong_text}")
        return " | ".join(parts)

    def parse_periods(self, tiet_str):
        periods = set()
        if not tiet_str:
            return periods
        tiet_str = str(tiet_str)
        parts = tiet_str.split(',')
        for part in parts:
            part = part.strip()
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    periods.update(range(start, end + 1))
                except Exception:
                    pass
            else:
                try:
                    periods.add(int(part))
                except Exception:
                    pass
        return periods

    def get_conflict_details(self, details_a):
        # Checks if details_a (scanned class) conflicts with any registered classes
        # Returns a dict: {"conflicting": True, "conflict_with": "Môn B [Lớp Y]"} or {"conflicting": False}
        if not details_a or not self.registered_classes_schedules:
            return {"conflicting": False}
            
        for sa in details_a:
            thu_a = str(sa.get("thu", ""))
            periods_a = self.parse_periods(sa.get("tietHoc", ""))
            if not thu_a or not periods_a:
                continue
                
            for rc_id, info in self.registered_classes_schedules.items():
                rc_name = info.get("name", "Môn học đã đăng ký")
                rc_code = info.get("code", "")
                rc_schedules = info.get("schedules", [])
                
                for sb in rc_schedules:
                    thu_b = str(sb.get("thu", ""))
                    periods_b = self.parse_periods(sb.get("tietHoc", ""))
                    if not thu_b or not periods_b:
                        continue
                        
                    if thu_a == thu_b:
                        if periods_a.intersection(periods_b):
                            return {
                                "conflicting": True,
                                "conflict_with": f"{rc_name} (Lớp {rc_code})"
                            }
        return {"conflicting": False}

    def check_filter(self, details, target_thu, target_ca):
        if not details:
            return False
        if target_thu == "Tất cả" and target_ca == "Tất cả":
            return True
        for d in details:
            raw_thu = str(d.get('thu', ''))
            is_cn = raw_thu in ['8', 'CN', 'Chủ Nhật']
            current_thu = "Chủ nhật" if is_cn else f"Thứ {raw_thu}"
            
            match_thu = (target_thu == "Tất cả") or (target_thu.lower() == current_thu.lower())
            match_ca = (target_ca == "Tất cả")
            
            if target_ca != "Tất cả":
                tiet_str = d.get('tietHoc', '')
                t_s, t_e = CA_HOC[target_ca][0], CA_HOC[target_ca][-1]
                if f"{t_s}-{t_e}" in tiet_str or f"{t_s},{t_e}" in tiet_str:
                    match_ca = True
                else:
                    try:
                        if '-' in tiet_str:
                            start, end = map(int, tiet_str.split('-'))
                            if t_s <= start <= t_e:
                                match_ca = True
                    except Exception:
                        pass
            if match_thu and match_ca:
                return True
        return False

    def run_spam_loop(self, targets, mode="normal"):
        self.is_spamming = True
        self.stats = {"total_requests": 0, "success_count": 0, "error_count": 0}
        self.log(f"🔥 Bắt đầu chiến dịch Spam {len(targets)} lớp ở chế độ {mode.upper()}...")

        def register_class(t):
            if not self.is_spamming:
                return None
            try:
                is_cond = t.get('is_conditional', False)
                if is_cond:
                    url = "https://portal.ut.edu.vn/api/v1/dkhpdk/dangKyLopHocPhan"
                else:
                    url = "https://portal.ut.edu.vn/api/v1/dkhp/dangKyLopHocPhan"
                    
                params = {
                    "idLopHocPhan": str(t['id']),
                    "g-recaptcha-response": ""
                }
                resp = self.request_with_retry("POST", url, params=params, timeout=5)
                self.stats["total_requests"] += 1
                
                if resp.status_code == 200:
                    d = resp.json()
                    msg = d.get("message", "")
                    if d.get("success"):
                        self.log(f"🎉 ĐĂNG KÝ THÀNH CÔNG: {t['name']} (ID: {t['id']})")
                        self.stats["success_count"] += 1
                        return {"status": "success", "target": t}
                    elif "đã đăng ký" in msg or "Trùng lịch học" in msg:
                        self.log(f"ℹ️ {t['name']}: {msg}")
                        self.stats["success_count"] += 1
                        return {"status": "already", "target": t}
                    else:
                        self.log(f"⚠️ {t['name']}: {msg}")
                        self.stats["error_count"] += 1
                        return {"status": "failed", "target": t}
                elif resp.status_code == 401:
                    self.log("💀 Token hết hạn! Vui lòng đăng nhập lại.")
                    self.is_spamming = False
                    return {"status": "expired", "target": t}
                else:
                    self.log(f"🔥 Lỗi HTTP {resp.status_code} khi đăng ký {t['name']}")
                    self.stats["error_count"] += 1
                    return {"status": "failed", "target": t}
            except Exception as e:
                self.log(f"❌ Lỗi mạng khi đăng ký {t['name']}: {e}")
                self.stats["error_count"] += 1
                return {"status": "failed", "target": t}

        while self.is_spamming and targets:
            next_round = []
            
            if mode == "turbo":
                max_workers = min(len(targets) * 2, 12)
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(register_class, t): t for t in targets}
                    for future in concurrent.futures.as_completed(futures):
                        res = future.result()
                        if res and res["status"] == "failed":
                            next_round.append(res["target"])
                
                if self.is_spamming and next_round:
                    time.sleep(0.1)
            else:
                for t in targets:
                    if not self.is_spamming:
                        break
                    res = register_class(t)
                    if res and res["status"] == "failed":
                        next_round.append(res["target"])
                    time.sleep(0.5)
                
                if self.is_spamming and next_round:
                    time.sleep(1.0)

            targets = next_round

        self.log("⏹ Đã dừng Spam.")
        self.is_spamming = False
