from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os
import threading
import time
import requests
import sys
from auto_config import get_auto_config
import urllib3.util.connection as connection
import socket

# Dynamic DNS Caching for UTH Portal to eliminate DNS lookup latency
dns_cache = {}
original_create_connection = connection.create_connection

def custom_create_connection(address, *args, **kwargs):
    host, port = address
    if host == "portal.ut.edu.vn":
        if host not in dns_cache:
            try:
                ips = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
                if ips:
                    resolved_ip = ips[0][4][0]
                    dns_cache[host] = resolved_ip
                    print(f"📡 [DNS Cache] Resolved {host} -> {resolved_ip}")
            except Exception as e:
                print(f"⚠️ [DNS Cache] Failed to resolve {host}: {e}")
        
        if host in dns_cache:
            return original_create_connection((dns_cache[host], port), *args, **kwargs)
            
    return original_create_connection(address, *args, **kwargs)

connection.create_connection = custom_create_connection
# Import ca hoc mapping
CA_HOC = {
    "Ca 1 (Tiết 1-3)":   [1, 2, 3],
    "Ca 2 (Tiết 4-6)":   [4, 5, 6],
    "Ca 3 (Tiết 7-9)":   [7, 8, 9],
    "Ca 4 (Tiết 10-12)": [10, 11, 12],
    "Ca 5 (Tiết 13-15)": [13, 14, 15]
}

# Cấu hình thư mục chứa static files của React frontend
dist_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")
if not os.path.exists(dist_folder):
    dist_folder = os.path.join(sys._MEIPASS, "frontend", "dist") if hasattr(sys, "_MEIPASS") else "dist"

app = Flask(__name__, static_folder=dist_folder, static_url_path="/")
CORS(app)  # Enable CORS for frontend

@app.route("/")
def serve_index():
    if os.path.exists(os.path.join(app.static_folder, "index.html")):
        return app.send_static_file("index.html")
    return "SmartEnroll API Server is running. Static frontend not found."

@app.after_request
def add_header(r):
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    return r

# Lưu config vào thư mục home của người dùng để tránh lỗi phân quyền (Read-only AppTranslocation) khi đóng gói trên macOS/Windows
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".smartenroll_config.json")

class AppState:
    def __init__(self):
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
        self.auto_config_status = "idle"  # idle, running, success, failed
        self.session = requests.Session()
        # Tăng kích thước Pool để tối ưu hóa kết nối song song và tái sử dụng Keep-Alive
        adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=200, max_retries=1)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.config = None
        self.load_config_data()

    def load_config_data(self):
        # Tự động di chuyển config.json cũ sang thư mục home nếu chưa di chuyển
        if not os.path.exists(CONFIG_FILE) and os.path.exists("config.json"):
            try:
                import shutil
                shutil.copy("config.json", CONFIG_FILE)
                self.log(f"Đã tự động di chuyển config.json sang {CONFIG_FILE}")
            except Exception as e:
                self.log(f"Lỗi khi di chuyển config.json: {e}")

        # Caching variables to keep token/cookie across manual/auto updates if not supplied
        if not hasattr(self, '_token_cache'):
            self._token_cache = None
        if not hasattr(self, '_cookie_cache'):
            self._cookie_cache = None
        if not hasattr(self, '_ua_cache'):
            self._ua_cache = None

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
                    
                    # Update caches if the loaded ones are present
                    if self.config.get('token'):
                        self._token_cache = self.config.get('token')
                    if self.config.get('cookie'):
                        self._cookie_cache = self.config.get('cookie')
                    if self.config.get('user_agent'):
                        self._ua_cache = self.config.get('user_agent')
                        
                    # Backfill empty fields from cache if present
                    if not self.config.get('token') and self._token_cache:
                        self.config['token'] = self._token_cache
                    if not self.config.get('cookie') and self._cookie_cache:
                        self.config['cookie'] = self._cookie_cache
                    if not self.config.get('user_agent') and self._ua_cache:
                        self.config['user_agent'] = self._ua_cache
                        
                    self.update_session_headers()
                    return True
            except Exception as e:
                self.log(f"Lỗi đọc config.json: {e}")
        self.config = None
        return False

    def update_session_headers(self):
        if self.config:
            self.session.headers.update({
                "Authorization": f"Bearer {self.config.get('token', '')}",
                "Cookie": self.config.get('cookie', ''),
                "User-Agent": self.config.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            })

    def login_with_credentials(self, username, password):
        url = "https://portal.ut.edu.vn/api/v1/auth/login"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        payload = {
            "username": username,
            "password": password
        }
        try:
            self.session.cookies.clear()
            self.session.headers.clear()
            resp = self.session.post(url, json=payload, headers=headers, timeout=10, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success") and data.get("token"):
                    token = data.get("token")
                    cookie_str = "; ".join([f"{k}={v}" for k, v in self.session.cookies.items()])
                    
                    self.config = {
                        "api_url": "https://portal.ut.edu.vn/coursesregistration",
                        "token": token,
                        "cookie": cookie_str,
                        "id_dot": self.config.get("id_dot", "76") if self.config else "76",
                        "user_agent": headers["User-Agent"],
                        "username": username,
                        "password": password
                    }
                    
                    # Update cache values
                    self._token_cache = token
                    self._cookie_cache = cookie_str
                    
                    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                        json.dump(self.config, f, indent=4)
                    self.update_session_headers()
                    self.log(f"🔑 Đăng nhập thành công tài khoản: {username}!")
                    return True
                else:
                    self.log(f"❌ Đăng nhập thất bại: {data.get('message')}")
            else:
                self.log(f"❌ Đăng nhập thất bại, mã lỗi: {resp.status_code}")
        except Exception as e:
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

    def run_auto_config_bg(self):
        self.is_auto_configuring = True
        self.auto_config_status = "running"
        self.log("🚀 Đang khởi động auto_config qua Chrome...")
        
        try:
            res = get_auto_config()
            if res:
                self.auto_config_status = "success"
                self.log("✅ Lấy Token & ID đợt đăng ký thành công!")
                self.load_config_data()
            else:
                self.auto_config_status = "failed"
                self.log("❌ Lấy cấu hình thất bại (Trình duyệt đóng hoặc hết thời gian).")
        except Exception as e:
            self.auto_config_status = "failed"
            self.log(f"❌ Lỗi khi chạy auto config: {e}")
        finally:
            self.is_auto_configuring = False

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

        import concurrent.futures

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
                # TURBO MODE: Spam concurrently using ThreadPool
                max_workers = min(len(targets) * 2, 12)
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(register_class, t): t for t in targets}
                    for future in concurrent.futures.as_completed(futures):
                        res = future.result()
                        if res and res["status"] == "failed":
                            next_round.append(res["target"])
                
                if self.is_spamming and next_round:
                    time.sleep(0.1) # Tiny sleep to avoid CPU lockup but stay ultra-fast
            else:
                # NORMAL MODE: Sequential, 0.5s delay
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

state = AppState()

# Vô hiệu hóa bộ nhớ đệm (Cache) của trình duyệt đối với các API
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# --- API ENDPOINTS ---

@app.route('/api/config', methods=['GET'])
def get_config():
    state.load_config_data()
    return jsonify({
        "config": state.config,
        "exists": state.config is not None
    })

@app.route('/api/config/manual', methods=['POST'])
def save_config_manual():
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "Dữ liệu trống!"}), 400
    
    config_data = {
        "api_url": "https://portal.ut.edu.vn/coursesregistration",
        "token": data.get("token", "").strip(),
        "cookie": data.get("cookie", "").strip(),
        "id_dot": data.get("id_dot", "").strip(),
        "user_agent": data.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "username": data.get("username", "").strip(),
        "password": data.get("password", "").strip()
    }
    
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
        state.load_config_data()
        return jsonify({"success": True, "message": "Lưu cấu hình thành công!"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Không thể lưu cấu hình: {e}"}), 500
@app.route('/api/config/login', methods=['POST'])
def login_portal():
    data = request.json
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"success": False, "message": "Thiếu tài khoản hoặc mật khẩu!"}), 400
    
    username = data.get("username").strip()
    password = data.get("password").strip()
    
    if state.login_with_credentials(username, password):
        return jsonify({"success": True, "message": "Đăng nhập thành công!", "config": state.config})
    else:
        return jsonify({"success": False, "message": "Sai tài khoản hoặc mật khẩu, hoặc hệ thống trường lỗi!"}), 401

@app.route('/api/config/logout', methods=['POST'])
def logout_portal():
    try:
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        state.config = None
        state.session.cookies.clear()
        state.session.headers.clear()
        return jsonify({"success": True, "message": "Đăng xuất thành công!"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Không thể đăng xuất: {e}"}), 500
@app.route('/api/config/auto', methods=['POST'])
def start_auto_config():
    if state.is_auto_configuring:
        return jsonify({"success": False, "message": "Đang chạy auto config..."})
    
    state.auto_config_thread = threading.Thread(target=state.run_auto_config_bg, daemon=True)
    state.auto_config_thread.start()
    return jsonify({"success": True, "message": "Đã khởi động tiến trình quét tự động..."})

@app.route('/api/config/auto/status', methods=['GET'])
def get_auto_config_status():
    return jsonify({
        "status": state.auto_config_status,
        "running": state.is_auto_configuring
    })

@app.route('/api/courses', methods=['GET'])
def get_courses():
    if not state.config:
        return jsonify({"success": False, "message": "Cấu hình chưa được tải!"}), 400
    
    reg_type = request.args.get('type', 'new')  # new, repeat, improve
    id_dot = request.args.get('idDot', state.config.get('id_dot'))
    
    if reg_type == 'repeat':
        url = "https://portal.ut.edu.vn/api/v1/dkhp/getHocPhanHocLai"
    elif reg_type == 'improve':
        url = "https://portal.ut.edu.vn/api/v1/dkhp/getHocPhanCaiThien"
    elif reg_type == 'cond_new':
        url = "https://portal.ut.edu.vn/api/v1/dkhpdk/getHocPhanHocMoi"
    elif reg_type == 'cond_repeat' or reg_type == 'conditional':
        url = "https://portal.ut.edu.vn/api/v1/dkhpdk/getHocPhanHocLai"
    else:
        url = "https://portal.ut.edu.vn/api/v1/dkhp/getHocPhanHocMoi"
        
    params = {"idDot": id_dot}
    
    try:
        resp = state.request_with_retry("GET", url, params=params, timeout=10)
        if resp.status_code == 200:
            subjects = resp.json().get('data') or resp.json().get('body') or []
            return jsonify({"success": True, "data": subjects})
        elif resp.status_code == 401:
            return jsonify({"success": False, "message": "Token hết hạn!", "expired": True}), 401
        else:
            return jsonify({"success": False, "message": f"Portal trả về mã {resp.status_code}"}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi kết nối portal: {e}"}), 500

@app.route('/api/dots', methods=['GET'])
def get_dots():
    if not state.config:
        return jsonify({"success": False, "message": "Cấu hình chưa được tải!"}), 400
        
    reg_type = request.args.get('type', 'normal')
    if reg_type == 'conditional':
        url = "https://portal.ut.edu.vn/api/v1/dkhpdk/getDot"
    else:
        url = "https://portal.ut.edu.vn/api/v1/dkhp/getDot"
        
    try:
        resp = state.request_with_retry("GET", url, timeout=10)
        if resp.status_code == 200:
            dots = resp.json().get('data') or resp.json().get('body') or []
            return jsonify({"success": True, "data": dots})
        elif resp.status_code == 401:
            return jsonify({"success": False, "message": "Token hết hạn!", "expired": True}), 401
        else:
            return jsonify({"success": False, "message": f"Portal trả về mã {resp.status_code}"}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi kết nối portal: {e}"}), 500

@app.route('/api/registered', methods=['GET'])
def get_registered_classes():
    if not state.config:
        return jsonify({"success": False, "message": "Cấu hình chưa được tải!"}), 400
        
    id_dot = request.args.get('idDot', state.config.get('id_dot'))
    url_normal = "https://portal.ut.edu.vn/api/v1/dkhp/getLHPDaDangKy"
    url_cond = "https://portal.ut.edu.vn/api/v1/dkhpdk/getLHPDaDangKy"
    params = {"idDot": id_dot}
    
    registered = []
    
    # 1. Fetch normal registered classes
    try:
        resp_n = state.request_with_retry("GET", url_normal, params=params, timeout=10)
        if resp_n.status_code == 200:
            normal_data = resp_n.json().get('data') or resp_n.json().get('body') or []
            for item in normal_data:
                item['isConditional'] = False
                registered.append(item)
        elif resp_n.status_code == 401:
            return jsonify({"success": False, "message": "Token hết hạn!", "expired": True}), 401
    except Exception as e:
        print("Lỗi fetch registered normal:", e)
        
    # 2. Fetch conditional registered classes
    try:
        resp_c = state.request_with_retry("GET", url_cond, params=params, timeout=10)
        if resp_c.status_code == 200:
            cond_data = resp_c.json().get('data') or resp_c.json().get('body') or []
            for item in cond_data:
                item['isConditional'] = True
                registered.append(item)
    except Exception as e:
        print("Lỗi fetch registered conditional:", e)
        
    return jsonify({"success": True, "data": registered})

@app.route('/api/deregister', methods=['POST'])
def deregister_class():
    if not state.config:
        return jsonify({"success": False, "message": "Cấu hình chưa được tải!"}), 400
        
    id_dang_ky = request.json.get('idDangKy')
    is_conditional = request.json.get('isConditional', False)
    if not id_dang_ky:
        return jsonify({"success": False, "message": "Thiếu mã đăng ký (idDangKy)!"}), 400
        
    if is_conditional:
        url = "https://portal.ut.edu.vn/api/v1/dkhpdk/huyDangKy"
    else:
        url = "https://portal.ut.edu.vn/api/v1/dkhp/huyDangKy"
        
    params = {"idDangKy": str(id_dang_ky)}
    
    try:
        resp = state.request_with_retry("DELETE", url, params=params, timeout=10)
        if resp.status_code == 200:
            return jsonify(resp.json())
        elif resp.status_code == 401:
            return jsonify({"success": False, "message": "Token hết hạn!", "expired": True}), 401
        else:
            return jsonify({"success": False, "message": f"Portal trả về mã {resp.status_code}"}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi kết nối portal: {e}"}), 500


@app.route('/api/classes', methods=['GET'])
def get_classes():
    if not state.config:
        return jsonify({"success": False, "message": "Cấu hình chưa được tải!"}), 400
    
    ma_hp = request.args.get('maHocPhan')
    target_thu = request.args.get('thu', 'Tất cả')
    target_ca = request.args.get('ca', 'Tất cả')
    id_dot = request.args.get('idDot', state.config.get('id_dot'))
    is_conditional = request.args.get('isConditional', 'false') == 'true'
    
    if not ma_hp:
        return jsonify({"success": False, "message": "Thiếu mã học phần!"}), 400

    if is_conditional:
        url_list = "https://portal.ut.edu.vn/api/v1/dkhpdk/getLopHocPhan"
    else:
        url_list = "https://portal.ut.edu.vn/api/v1/dkhp/getLopHocPhanChoDangKy"
        
    params = {
        "idDot": id_dot,
        "maHocPhan": ma_hp,
        "isLocTrung": "false",
        "isLocTrungWithoutElearning": "false"
    }

    try:
        resp = state.request_with_retry("GET", url_list, params=params, timeout=10)
        if resp.status_code != 200:
            return jsonify({"success": False, "message": f"Không thể lấy danh sách lớp, mã {resp.status_code}"}), resp.status_code
        
        classes = resp.json().get('data') or resp.json().get('body') or []
        filtered_classes = []
        
        for cls in classes:
            cls_id = cls.get('id')
            details = state.fetch_class_detail(cls_id, is_conditional)
            
            if state.check_filter(details, target_thu, target_ca):
                schedule = state.format_schedule(details)
                percent = cls.get('phanTramDangKy', 0.0)
                cho_dk = cls.get('choDangKy', True)
                status_text = f"{percent}%"
                if percent >= 100 or not cho_dk:
                    status_text += " (FULL)"
                
                filtered_classes.append({
                    "id": cls_id,
                    "maLopHocPhan": cls.get('maLopHocPhan'),
                    "tenMonHoc": cls.get('tenMonHoc') or cls.get('tenHocPhan'),
                    "schedule": schedule,
                    "status": status_text,
                    "capacity_percent": percent,
                    "open": cho_dk
                })
                time.sleep(0.05) # Tiny sleep to prevent school server spam during query
                
        return jsonify({"success": True, "data": filtered_classes})
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi truy quét lớp: {e}"}), 500

@app.route('/api/spam/start', methods=['POST'])
def start_spam():
    if state.is_spamming:
        return jsonify({"success": False, "message": "Spam đang chạy rồi!"})
    
    data = request.json
    targets = data.get("targets", [])
    mode = data.get("mode", "normal")
    if not targets:
        return jsonify({"success": False, "message": "Danh sách đăng ký trống!"}), 400
        
    state.spam_thread = threading.Thread(target=state.run_spam_loop, args=(targets, mode), daemon=True)
    state.spam_thread.start()
    return jsonify({"success": True, "message": f"Đã bắt đầu spam ở chế độ {mode.upper()}..."})

@app.route('/api/spam/stop', methods=['POST'])
def stop_spam():
    state.is_spamming = False
    return jsonify({"success": True, "message": "Yêu cầu dừng spam đã được gửi."})

@app.route('/api/spam/status', methods=['GET'])
def get_spam_status():
    return jsonify({
        "is_spamming": state.is_spamming,
        "stats": state.stats,
        "logs": state.logs[-50:]  # Return last 50 logs to frontend
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    state.log(f"🔥 API Server đang chạy tại http://localhost:{port}")
    
    # Tự động mở trình duyệt sau khi Flask khởi động
    import webbrowser
    def open_browser():
        time.sleep(1.5)
        try:
            webbrowser.open(f"http://localhost:{port}")
        except Exception:
            pass
    threading.Thread(target=open_browser, daemon=True).start()
    
    app.run(host='0.0.0.0', port=port, debug=False)
