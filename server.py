from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os
import threading
import time
import requests
import sys
from auto_config import get_auto_config

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

CONFIG_FILE = "config.json"

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
        self.config = None
        self.load_config_data()

    def load_config_data(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
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

    def fetch_class_detail(self, class_id):
        url = "https://portal.ut.edu.vn/api/v1/dkhp/getLopHocPhanDetail"
        params = {"idLopHocPhan": class_id}
        for _ in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=5)
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

    def run_spam_loop(self, targets):
        self.is_spamming = True
        self.stats = {"total_requests": 0, "success_count": 0, "error_count": 0}
        self.log(f"🔥 Bắt đầu chiến dịch Spam {len(targets)} lớp học phần...")
        url = "https://portal.ut.edu.vn/api/v1/dkhp/dangKyLopHocPhan"

        while self.is_spamming and targets:
            next_round = []
            for t in targets:
                if not self.is_spamming:
                    break
                try:
                    self.stats["total_requests"] += 1
                    params = {
                        "idLopHocPhan": str(t['id']),
                        "g-recaptcha-response": ""
                    }
                    resp = self.session.post(url, params=params, timeout=5)
                    
                    if resp.status_code == 200:
                        d = resp.json()
                        msg = d.get("message", "")
                        if d.get("success"):
                            self.log(f"🎉 ĐĂNG KÝ THÀNH CÔNG: {t['name']} (ID: {t['id']})")
                            self.stats["success_count"] += 1
                        elif "đã đăng ký" in msg or "Trùng lịch học" in msg:
                            self.log(f"ℹ️ {t['name']}: {msg}")
                            self.stats["success_count"] += 1  # count as success since we don't need to register again
                        else:
                            self.log(f"⚠️ {t['name']}: {msg}")
                            next_round.append(t)
                            self.stats["error_count"] += 1
                    elif resp.status_code == 401:
                        self.log("💀 Token hết hạn! Vui lòng làm mới cấu hình.")
                        self.is_spamming = False
                        break
                    else:
                        self.log(f"🔥 Lỗi HTTP {resp.status_code} khi đăng ký {t['name']}")
                        next_round.append(t)
                        self.stats["error_count"] += 1
                except Exception as e:
                    self.log(f"❌ Lỗi mạng khi đăng ký {t['name']}: {e}")
                    next_round.append(t)
                    self.stats["error_count"] += 1
                time.sleep(0.5)  # Rest to avoid rate limit / IP block
            
            targets = next_round
            if self.is_spamming and targets:
                time.sleep(1.5)

        self.log("⏹ Đã dừng Spam.")
        self.is_spamming = False

state = AppState()

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
        "user_agent": data.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    }
    
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
        state.load_config_data()
        return jsonify({"success": True, "message": "Lưu cấu hình thành công!"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Không thể lưu cấu hình: {e}"}), 500

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
    
    url = "https://portal.ut.edu.vn/api/v1/dkhp/getHocPhanHocMoi"
    params = {"idDot": state.config.get('id_dot')}
    
    try:
        resp = state.session.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            subjects = resp.json().get('data') or resp.json().get('body') or []
            return jsonify({"success": True, "data": subjects})
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
    
    if not ma_hp:
        return jsonify({"success": False, "message": "Thiếu mã học phần!"}), 400

    url_list = "https://portal.ut.edu.vn/api/v1/dkhp/getLopHocPhanChoDangKy"
    params = {
        "idDot": state.config.get('id_dot'),
        "maHocPhan": ma_hp,
        "isLocTrung": "false",
        "isLocTrungWithoutElearning": "false"
    }

    try:
        resp = state.session.get(url_list, params=params, timeout=10)
        if resp.status_code != 200:
            return jsonify({"success": False, "message": f"Không thể lấy danh sách lớp, mã {resp.status_code}"}), resp.status_code
        
        classes = resp.json().get('data') or resp.json().get('body') or []
        filtered_classes = []
        
        for cls in classes:
            cls_id = cls.get('id')
            details = state.fetch_class_detail(cls_id)
            
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
    if not targets:
        return jsonify({"success": False, "message": "Danh sách đăng ký trống!"}), 400
        
    state.spam_thread = threading.Thread(target=state.run_spam_loop, args=(targets,), daemon=True)
    state.spam_thread.start()
    return jsonify({"success": True, "message": "Đã bắt đầu spam..."})

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
