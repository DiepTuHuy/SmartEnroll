from flask import Flask, jsonify, request, make_response, send_from_directory
from flask_cors import CORS
import json
import os
import threading
import time
import requests
import sys
import random
import string
from auto_config import get_auto_config
import urllib3.util.connection as connection
import socket

# Dynamic DNS Caching for UTH Portal to eliminate DNS lookup latency
dns_cache = {}
original_create_connection = connection.create_connection

def custom_create_connection(address, *args, **kwargs):
    host, port = address
    if host == "portal.ut.edu.vn" and host in dns_cache:
        address = (dns_cache[host], port)
    return original_create_connection(address, *args, **kwargs)

connection.create_connection = custom_create_connection

def resolve_dns_early():
    try:
        ip = socket.gethostbyname("portal.ut.edu.vn")
        dns_cache["portal.ut.edu.vn"] = ip
        print(f"📡 [DNS Cache] Resolved portal.ut.edu.vn -> {ip}")
    except Exception as e:
        print(f"⚠️ [DNS Cache] Failed to resolve portal.ut.edu.vn: {e}")

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

import logging

class _QuietPollingLog(logging.Filter):
    """Ẩn log truy cập của các API mà giao diện hỏi liên tục (mỗi 1-30 giây).

    Treo máy vài giờ chờ đăng ký sẽ tạo hàng nghìn dòng vô ích trên console.
    Các request khác (đăng nhập, quét lớp, đăng ký...) vẫn được log bình thường.
    """
    NOISY = ('"GET /api/spam/status ', '"GET /api/config ', '"GET /api/config/login/status ',
             '"GET /api/config/auto/status ', '"GET /api/share/status ')

    def filter(self, record):
        message = record.getMessage()
        return not any(path in message for path in self.NOISY)

logging.getLogger("werkzeug").addFilter(_QuietPollingLog())

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

@app.route("/")
def serve_index():
    index_path = os.path.join(app.static_folder, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        buster = str(int(time.time()))
        # Inject cache buster to script src and link href
        html = html.replace('.js"', f'.js?v={buster}"')
        html = html.replace('.css"', f'.css?v={buster}"')
        
        response = make_response(html)
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
    return "SmartEnroll API Server is running. Static frontend not found."

@app.after_request
def add_header(r):
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    return r

from core_state import get_app_state
state = get_app_state('web_default')

PORTAL_STATUS_HINTS = {
    403: "cổng trường từ chối truy cập. Hay gặp khi đợt đăng ký chưa mở hoặc đã đóng, đợt này không dành cho bạn, "
         "hoặc bị chặn tạm thời vì gửi quá nhiều request",
    404: "không tìm thấy dữ liệu (có thể sai ID đợt học)",
    429: "cổng trường báo gửi quá nhiều request, hãy chờ một lúc rồi thử lại",
}

def portal_error_response(resp, prefix):
    """Báo lỗi kèm NGUYÊN VĂN lời cổng trường. Bản cũ chỉ ghi "mã 403", không cho biết vì sao bị từ chối."""
    detail = ""
    try:
        body = resp.json()
        if isinstance(body, dict):
            detail = str(body.get("message") or body.get("error") or body.get("title") or "")
    except ValueError:
        text = (resp.text or "").strip()
        if text and not text.startswith("<"):
            detail = text[:200]
    code = resp.status_code
    message = f"{prefix} (mã {code})"
    if detail:
        message += f": {detail}"
    elif code in PORTAL_STATUS_HINTS:
        message += f": {PORTAL_STATUS_HINTS[code]}"
    endpoint = resp.url.split("?")[0].replace("https://portal.ut.edu.vn", "")
    state.log(f"⚠️ {message} [{endpoint}]")
    return jsonify({"success": False, "message": message, "status": code}), code

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
        "exists": state.config is not None,
        # Token cổng trường sống 30 ngày: UI dùng để báo "không cần đăng nhập lại".
        "token_expires_at": state.token_expires_at(),
        # Kết quả hỏi cổng trường gần nhất (True/False/None) và thời điểm hỏi.
        "token_ok": state.token_ok,
        "token_checked_at": state.token_checked_at
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
        "password": data.get("password", "").strip(),
        "fb_username": data.get("fb_username", "").strip(),
        "fb_password": data.get("fb_password", "").strip()
    }
    
    try:
        state.save_config(config_data)
        return jsonify({"success": True, "message": "Lưu cấu hình thành công!"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Không thể lưu cấu hình: {e}"}), 500

@app.route('/api/config/login', methods=['POST'])
def login_portal():
    """Khởi động tiến trình đăng nhập NỀN rồi trả về ngay; UI hỏi tiến độ qua /api/config/login/status.

    Bản cũ giữ request HTTP mở trong lúc chờ cổng trường, nên khi cổng trường nghẽn
    thì trình duyệt/proxy bỏ cuộc trước và báo "Không thể kết nối đến server SmartEnroll".
    """
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    if not username or not password:
        return jsonify({"success": False, "message": "Thiếu tài khoản hoặc mật khẩu!"}), 400

    persistent = bool(data.get("persistent", True))
    ok, info = state.start_login_job(username, password, persistent=persistent)
    if not ok:
        return jsonify({"success": False, "message": info}), 409
    return jsonify({"success": True, "started": True, "message": "Đang đăng nhập cổng trường..."}), 202

@app.route('/api/config/login/status', methods=['GET'])
def login_portal_status():
    job = dict(state.login_job)
    now = time.time()
    next_retry_at = job.pop("next_retry_at", None)
    job["retry_in"] = max(0.0, next_retry_at - now) if next_retry_at else None
    if job.get("started_at"):
        job["elapsed"] = (job.get("finished_at") or now) - job["started_at"]
    if job.get("status") == "success":
        job["config"] = state.config
    return jsonify(job)

@app.route('/api/config/login/stop', methods=['POST'])
def login_portal_stop():
    state.stop_login_job()
    return jsonify({"success": True, "message": "Đã dừng đăng nhập."})

@app.route('/api/config/logout', methods=['POST'])
def logout_portal():
    try:
        state.stop_login_job()
        state.is_spamming = False
        if os.path.exists(state.config_file):
            os.remove(state.config_file)
        state.config = None
        state.session.cookies.clear()
        state.session.headers.pop("Authorization", None)
        state.session.headers.pop("Cookie", None)
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
            return portal_error_response(resp, "Không tải được danh sách môn")
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
            return portal_error_response(resp, "Không tải được danh sách đợt")
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
        
    # Tải lịch học chi tiết của các lớp đã đăng ký song song để làm cơ sở check trùng lịch
    if registered:
        import concurrent.futures
        def fetch_schedule(item):
            rc_id = item.get('id') or item.get('idDangKy')
            if not rc_id:
                return None
            try:
                # Cả môn điều kiện và môn thường đều dùng chung endpoint dkhp/getLichHoc
                url = "https://portal.ut.edu.vn/api/v1/dkhp/getLichHoc"
                resp = state.request_with_retry("GET", url, params={"idDangKy": str(rc_id)}, timeout=5)
                if resp.status_code == 200:
                    schedules = resp.json().get('body') or []
                    return rc_id, schedules
            except Exception as ex:
                print(f"Lỗi lấy lịch cho lớp {rc_id}:", ex)
            return rc_id, []

        schedules_map = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(registered), 10)) as executor:
            results = executor.map(fetch_schedule, registered)
            for res in results:
                if res:
                    rc_id, scheds = res
                    schedules_map[rc_id] = scheds

        # Lưu lịch học đã được cache lại vào AppState
        state.registered_classes_schedules = {}
        for item in registered:
            rc_id = item.get('id') or item.get('idDangKy')
            scheds = schedules_map.get(rc_id, [])
            item['schedules'] = scheds
            item['scheduleText'] = state.format_schedule(scheds)
            state.registered_classes_schedules[rc_id] = {
                "name": item.get('tenMonHoc') or item.get('tenLopHocPhan') or item.get('tenHocPhan'),
                "code": item.get('maLopHocPhan') or item.get('maHocPhan') or '',
                "schedules": scheds
            }
            
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
            return portal_error_response(resp, "Không hủy được đăng ký")
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
            return portal_error_response(resp, "Không lấy được danh sách lớp")
        
        classes = resp.json().get('data') or resp.json().get('body') or []
        filtered_classes = []

        # Tải lịch từng lớp song song (giới hạn 6 luồng): khi cổng trường chậm,
        # quét tuần tự 20 lớp có thể mất vài phút.
        import concurrent.futures
        def load_detail(cls):
            return cls, state.fetch_class_detail(cls.get('id'), is_conditional)
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, max(1, len(classes)))) as executor:
            detailed = list(executor.map(load_detail, classes))

        for cls, details in detailed:
            cls_id = cls.get('id')
            if state.check_filter(details, target_thu, target_ca):
                schedule = state.format_schedule(details)
                percent = cls.get('phanTramDangKy', 0.0)
                cho_dk = cls.get('choDangKy', True)
                status_text = f"{percent}%"
                if percent >= 100 or not cho_dk:
                    status_text += " (FULL)"
                
                conflict_info = state.get_conflict_details(details)
                is_conflicting = conflict_info.get("conflicting", False)
                conflict_with = conflict_info.get("conflict_with", "")

                filtered_classes.append({
                    "id": cls_id,
                    "maLopHocPhan": cls.get('maLopHocPhan'),
                    "tenMonHoc": cls.get('tenMonHoc') or cls.get('tenHocPhan'),
                    "schedule": schedule,
                    "status": status_text,
                    "capacity_percent": percent,
                    "open": cho_dk,
                    "is_conflicting": is_conflicting,
                    "conflict_with": conflict_with
                })

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

# --- FACEBOOK SHARE DRL ROUTES ---

# Global state for Facebook sharing process
share_process = {
    "status": "idle", # idle, running, success, error
    "step": "",
    "error": None
}

def run_fb_share_async(event_id, title):
    global share_process
    import subprocess
    
    python_exe = sys.executable or "python"
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "facebook_share.py")
    
    try:
        process = subprocess.Popen(
            [python_exe, script_path, str(event_id), title],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        for line in iter(process.stdout.readline, ""):
            line = line.strip()
            print(f"[facebook_share output] {line}")
            if line.startswith("[STATUS]"):
                status_val = line.replace("[STATUS]", "").strip()
                if status_val.startswith("ERROR:"):
                    share_process["status"] = "error"
                    share_process["error"] = status_val.replace("ERROR:", "").strip()
                    share_process["step"] = ""
                elif status_val.startswith("SUCCESS:"):
                    filename = status_val.replace("SUCCESS:", "").strip()
                    share_process["status"] = "success"
                    share_process["step"] = f"Hoàn thành! Đã lưu minh chứng: {filename}"
                    share_process["error"] = None
                else:
                    steps_map = {
                        "STARTING_CHROME": "Đang khởi động trình duyệt Chrome...",
                        "LOGGING_IN_PORTAL": "Đang đăng nhập Cổng thông tin UTH...",
                        "LOADING_PORTAL_EVENT": "Đang ghi nhận sự kiện trên Portal...",
                        "NAVIGATING_FACEBOOK": "Đang kết nối Facebook...",
                        "LOGGING_IN_FB": "Đang điền thông tin và tự động đăng nhập Facebook...",
                        "WAITING_FB_REDIRECT": "Đang đợi Facebook chuyển hướng sau đăng nhập...",
                        "CHECKING_FB_LOGIN": "Đang kiểm tra đăng nhập Facebook...",
                        "WAITING_FB_LOGIN": "⚠️ Đang đợi bạn đăng nhập tài khoản Facebook trên trình duyệt Chrome vừa mở...",
                        "SEARCHING_FB": "Đang tìm kiếm bài viết sự kiện trên Facebook...",
                        "FINDING_POST": "Đang phân tích kết quả tìm kiếm...",
                        "SHARING_POST": "Đang nhấp nút Chia sẻ bài viết...",
                        "CONFIRMING_SHARE": "Đang xác nhận chia sẻ lên trang cá nhân...",
                        "TAKING_SCREENSHOT": "Đang chụp ảnh màn hình lưu minh chứng..."
                    }
                    share_process["status"] = "running"
                    share_process["step"] = steps_map.get(status_val, status_val)
                    
        process.stdout.close()
        process.wait()
        
        if process.returncode != 0 and share_process["status"] == "running":
            share_process["status"] = "error"
            share_process["error"] = f"Tiến trình bị gián đoạn với mã thoát {process.returncode}"
            
    except Exception as e:
        share_process["status"] = "error"
        share_process["error"] = str(e)

@app.route('/api/announcements', methods=['GET'])
def get_announcements():
    if not state.config:
        return jsonify({"success": False, "message": "Cấu hình chưa được tải!"}), 400
        
    username = state.config.get("username")
    password = state.config.get("password")
    
    if not username or not password:
        return jsonify({"success": False, "message": "Tài khoản/Mật khẩu trống!"}), 400
        
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1200,800")
    
    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.get("https://portal.ut.edu.vn/")
        time.sleep(3)
        
        if "/login" in driver.current_url or len(driver.find_elements(By.TAG_NAME, "input")) > 0:
            inputs = driver.find_elements(By.TAG_NAME, "input")
            for inp in inputs:
                type_attr = inp.get_attribute("type")
                placeholder = inp.get_attribute("placeholder") or ""
                if type_attr == "text" or "sinh viên" in placeholder.lower() or "mssv" in placeholder.lower() or "tài khoản" in placeholder.lower():
                    inp.clear()
                    inp.send_keys(username)
                elif type_attr == "password" or "mật khẩu" in placeholder.lower():
                    inp.clear()
                    inp.send_keys(password)
            
            time.sleep(0.5)
            buttons = driver.find_elements(By.TAG_NAME, "button")
            clicked = False
            for b in buttons:
                b_text = b.text.strip()
                if "Đăng nhập" in b_text or "ĐĂNG NHẬP" in b_text:
                    b.click()
                    clicked = True
                    break
            if not clicked:
                for b in buttons:
                    if b.get_attribute("type") == "submit" or "dang nhap" in b.text.lower():
                        b.click()
                        break
            time.sleep(5)
            
        driver.get("https://portal.ut.edu.vn/notedetail")
        time.sleep(3)
        
        links = driver.find_elements(By.TAG_NAME, "a")
        events = []
        drl_folder = os.path.join(os.getcwd(), "DRL")
        os.makedirs(drl_folder, exist_ok=True)
        
        for l in links:
            href = l.get_attribute("href") or ""
            text = l.text.strip()
            if "/event/" in href and text:
                event_id = href.split("/event/")[-1]
                
                shared_status = "not_shared"
                screenshot_file = None
                for fname in os.listdir(drl_folder):
                    if fname.startswith(f"share_event_{event_id}_") and fname.endswith(".png"):
                        shared_status = "shared"
                        screenshot_file = fname
                        break
                        
                events.append({
                    "id": event_id,
                    "title": text,
                    "link": href,
                    "status": shared_status,
                    "screenshot": f"/drl/{screenshot_file}" if screenshot_file else None
                })
        
        seen = set()
        unique_events = []
        for e in events:
            if e["id"] not in seen:
                seen.add(e["id"])
                unique_events.append(e)
                
        return jsonify({"success": True, "data": unique_events})
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi cào thông báo: {str(e)}"}), 500
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

@app.route('/api/share/facebook', methods=['POST'])
def share_facebook():
    global share_process
    if share_process["status"] == "running":
        return jsonify({"success": False, "message": "Có một tiến trình chia sẻ đang chạy!"}), 400
        
    data = request.json
    event_id = data.get("eventId")
    title = data.get("title", "")
    
    if not event_id:
        return jsonify({"success": False, "message": "Thiếu ID sự kiện!"}), 400
        
    share_process = {
        "status": "running",
        "step": "Đang chuẩn bị tiến trình...",
        "error": None
    }
    
    threading.Thread(target=run_fb_share_async, args=(event_id, title), daemon=True).start()
    return jsonify({"success": True, "message": "Đã bắt đầu tiến trình chia sẻ Facebook!"})

@app.route('/api/share/status', methods=['GET'])
def get_share_status():
    global share_process
    return jsonify(share_process)

@app.route('/drl/<path:filename>')
def serve_drl_file(filename):
    drl_folder = os.path.join(os.getcwd(), "DRL")
    return send_from_directory(drl_folder, filename)

@app.route('/api/export', methods=['GET'])
def export_study_data():
    if not state.config:
        return jsonify({"success": False, "message": "Chưa đăng nhập!"}), 401
    try:
        from export_json import build_export_data
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        data = loop.run_until_complete(build_export_data(state))
        import json
        response = app.response_class(
            response=json.dumps(data, ensure_ascii=False, indent=4),
            status=200,
            mimetype='application/json'
        )
        response.headers["Content-Disposition"] = "attachment; filename=DuLieuHocTap.json"
        return response
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

def keep_machine_awake():
    """Không cho máy tự ngủ khi đang treo chờ giờ đăng ký (máy ngủ = mất mạng = không đăng ký được).

    Chỉ có hiệu lực khi server còn chạy; tắt server là máy ngủ bình thường lại.
    Không chặn được việc gập màn hình laptop.
    """
    import platform
    system = platform.system()
    try:
        if system == "Darwin":
            import subprocess
            # -i: chặn ngủ khi rảnh, -w: tự thôi khi tiến trình này kết thúc
            subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
            state.log("☕ Đã bật chống ngủ máy trong lúc server chạy.")
        elif system == "Windows":
            import ctypes
            ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
            state.log("☕ Đã bật chống ngủ máy trong lúc server chạy.")
    except Exception as e:
        state.log(f"⚠️ Không bật được chống ngủ máy: {e}. Hãy tự tắt chế độ ngủ khi treo máy chờ đăng ký.")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    state.log(f"🔥 API Server đang chạy tại http://localhost:{port}")
    keep_machine_awake()
    
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
