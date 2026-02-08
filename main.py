import tkinter as tk
from tkinter import ttk, messagebox
import requests
import json
import threading
import time
import random

# --- ĐỊNH NGHĨA CA HỌC ---
CA_HOC = {
    "Ca 1 (Tiết 1-3)":   [1, 2, 3],
    "Ca 2 (Tiết 4-6)":   [4, 5, 6],
    "Ca 3 (Tiết 7-9)":   [7, 8, 9],
    "Ca 4 (Tiết 10-12)": [10, 11, 12],
    "Ca 5 (Tiết 13-15)": [13, 14, 15]
}

def load_config():
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None

class UTHRegisterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AUTO ĐKHP V17 - UPDATE REQUEST (CÓ RECAPTCHA)")
        self.root.geometry("1200x750")
        
        self.config = load_config()
        if not self.config:
            messagebox.showerror("Lỗi", "Thiếu config.json! Chạy auto_config.py trước.")
            root.destroy()
            return

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.config['token']}",
            "Cookie": self.config['cookie'],
            "User-Agent": self.config['user_agent'],
            # "Content-Type": "application/json" # API mới dùng params, có thể không cần content-type json
        })
        
        self.is_spamming = False
        self.course_map = {} 
        
        self.setup_ui()
        self.root.after(100, self.load_courses_init)

    def setup_ui(self):
        style = ttk.Style()
        style.configure("Treeview", rowheight=30, font=('Arial', 10))
        style.configure("Treeview.Heading", font=('Arial', 10, 'bold'))

        # 1. KHUNG CHỌN MÔN
        frame_scan = ttk.LabelFrame(self.root, text="1. Tìm kiếm lớp (API Detail)", padding=10)
        frame_scan.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(frame_scan, text="Môn học:").grid(row=0, column=0, padx=5, sticky="w")
        self.cb_course_var = tk.StringVar()
        self.cb_course = ttk.Combobox(frame_scan, textvariable=self.cb_course_var, width=70)
        self.cb_course.grid(row=0, column=1, columnspan=4, padx=5, sticky="ew", pady=5)
        self.cb_course.set("⏳ Đang tải môn...")
        
        ttk.Label(frame_scan, text="Lọc Thứ:").grid(row=1, column=0, padx=5, sticky="w")
        self.cb_thu = ttk.Combobox(frame_scan, values=["Tất cả", "Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"], width=15, state="readonly")
        self.cb_thu.grid(row=1, column=1, padx=5, sticky="w")
        self.cb_thu.current(0)

        ttk.Label(frame_scan, text="Lọc Ca:").grid(row=1, column=2, padx=5, sticky="w")
        self.cb_ca = ttk.Combobox(frame_scan, values=["Tất cả"] + list(CA_HOC.keys()), width=20, state="readonly")
        self.cb_ca.grid(row=1, column=3, padx=5, sticky="w")
        self.cb_ca.current(0)

        self.btn_scan = ttk.Button(frame_scan, text="🔎 QUÉT CHI TIẾT", command=self.start_scan)
        self.btn_scan.grid(row=1, column=4, padx=10, sticky="ew")

        # 2. DANH SÁCH
        frame_list = ttk.LabelFrame(self.root, text="2. Kết quả (Tích chọn để Spam)", padding=10)
        frame_list.pack(fill="both", expand=True, padx=10, pady=5)

        tree_container = ttk.Frame(frame_list)
        tree_container.pack(fill="both", expand=True)

        columns = ("check", "id", "malop", "name", "info", "status")
        self.tree = ttk.Treeview(tree_container, columns=columns, show="headings", height=15)
        
        self.tree.heading("check", text="Chọn")
        self.tree.column("check", width=50, minwidth=50, anchor="center", stretch=False)
        self.tree.heading("id", text="ID Lớp")
        self.tree.column("id", width=80, minwidth=80, anchor="center", stretch=False)
        self.tree.heading("malop", text="Mã Lớp")
        self.tree.column("malop", width=120, minwidth=100, stretch=False)
        self.tree.heading("name", text="Tên Môn")
        self.tree.column("name", width=200, minwidth=150, stretch=False)
        self.tree.heading("info", text="Lịch Học")
        self.tree.column("info", width=400, minwidth=300, stretch=True)
        self.tree.heading("status", text="Sĩ số (%)")
        self.tree.column("status", width=120, minwidth=100, anchor="center", stretch=False)

        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        vsb.pack(side="right", fill="y")
        hsb = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree.xview)
        hsb.pack(side="bottom", fill="x")

        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind('<Button-1>', self.on_tree_click)

        # 3. SPAM
        frame_action = ttk.Frame(self.root, padding=10)
        frame_action.pack(fill="x")

        self.btn_spam = ttk.Button(frame_action, text="🚀 CHẠY SPAM (0)", command=self.toggle_spam)
        self.btn_spam.pack(side="left", fill="x", expand=True, padx=5)
        self.btn_clear = ttk.Button(frame_action, text="🗑️ Xóa chọn", command=self.clear_selection)
        self.btn_clear.pack(side="right", padx=5)

        # 4. LOG
        self.txt_log = tk.Text(self.root, height=10, font=("Consolas", 9))
        self.txt_log.pack(fill="x", padx=10, pady=5)

    def log(self, msg):
        self.txt_log.insert(tk.END, f"➤ {msg}\n")
        self.txt_log.see(tk.END)

    def fetch_class_detail(self, class_id):
        url = "https://portal.ut.edu.vn/api/v1/dkhp/getLopHocPhanDetail"
        params = {"idLopHocPhan": class_id}
        for _ in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=5)
                if resp.status_code == 200: return resp.json().get('body') or []
                time.sleep(0.1)
            except: pass
        return None

    def format_schedule(self, details):
        if not details: return "⚠️ Không lấy được lịch"
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
        if not details: return False
        if target_thu == "Tất cả" and target_ca == "Tất cả": return True
        for d in details:
            raw_thu = str(d.get('thu', ''))
            is_cn = raw_thu in ['8', 'CN', 'Chủ Nhật']
            current_thu = "Chủ nhật" if is_cn else f"Thứ {raw_thu}"
            match_thu = (target_thu == "Tất cả") or (target_thu.lower() == current_thu.lower())
            match_ca = (target_ca == "Tất cả")
            if target_ca != "Tất cả":
                tiet_str = d.get('tietHoc', '')
                t_s, t_e = CA_HOC[target_ca][0], CA_HOC[target_ca][-1]
                if f"{t_s}-{t_e}" in tiet_str or f"{t_s},{t_e}" in tiet_str: match_ca = True
                else:
                    try:
                        if '-' in tiet_str:
                            start, end = map(int, tiet_str.split('-'))
                            if t_s <= start <= t_e: match_ca = True
                    except: pass
            if match_thu and match_ca: return True
        return False

    def load_courses_init(self):
        threading.Thread(target=self._fetch_courses, daemon=True).start()

    def _fetch_courses(self):
        url = "https://portal.ut.edu.vn/api/v1/dkhp/getHocPhanHocMoi" 
        params = {"idDot": self.config['id_dot']}
        try:
            self.log("📡 Đang tải danh sách môn học...")
            resp = self.session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                subjects = resp.json().get('data') or resp.json().get('body') or []
                display = []
                self.course_map = {}
                for s in subjects:
                    ma = s.get('maHocPhan')
                    ten = s.get('tenHocPhan') or s.get('tenMonHoc')
                    lbl = f"[{ma}] {ten}" + (" (BẮT BUỘC)" if s.get('isBatBuoc') else "")
                    display.append(lbl)
                    self.course_map[lbl] = ma
                    self.course_map[ma] = ma
                display.sort(key=lambda x: "(BẮT BUỘC)" not in x)
                self.root.after(0, lambda: self.cb_course.config(values=display))
                self.root.after(0, lambda: self.cb_course.set("--- Chọn môn ---"))
                self.log(f"✅ Đã tải xong {len(subjects)} môn.")
            else: self.log(f"❌ Lỗi tải môn: {resp.status_code}")
        except Exception as e: self.log(f"❌ Lỗi: {e}")

    def start_scan(self):
        user_input = self.cb_course.get().strip()
        if not user_input or "---" in user_input:
            messagebox.showwarning("Lỗi", "Chọn môn đi bạn ơi!")
            return
        ma_hp = self.course_map.get(user_input)
        if not ma_hp:
             if "[" in user_input: ma_hp = user_input.split("]")[0].replace("[", "").strip()
             else: ma_hp = user_input
        self.btn_scan.config(state="disabled", text="⏳ Đang đào dữ liệu...")
        threading.Thread(target=self.scan_logic, args=(ma_hp,)).start()

    def scan_logic(self, ma_hp):
        try:
            url_list = "https://portal.ut.edu.vn/api/v1/dkhp/getLopHocPhanChoDangKy"
            params = {"idDot": self.config['id_dot'], "maHocPhan": ma_hp, "isLocTrung": "false", "isLocTrungWithoutElearning": "false"}
            self.log(f"📡 1. Lấy danh sách lớp: {ma_hp}")
            resp = self.session.get(url_list, params=params, timeout=10)
            classes = resp.json().get('data') or resp.json().get('body') or []
            if not classes:
                self.log("⚠️ Không có lớp nào mở.")
                self.reset_scan_btn(); return
            self.log(f"🔎 Tìm thấy {len(classes)} lớp. Đang gọi API chi tiết...")
            count_add = 0
            target_thu = self.cb_thu.get()
            target_ca = self.cb_ca.get()
            for cls in classes:
                cls_id = cls.get('id')
                details = self.fetch_class_detail(cls_id)
                if self.check_filter(details, target_thu, target_ca):
                    tkb_str = self.format_schedule(details)
                    percent = cls.get('phanTramDangKy', 0.0)
                    cho_dk = cls.get('choDangKy', True)
                    status_text = f"{percent}%"
                    if percent >= 100 or not cho_dk: status_text += " (FULL)"
                    exists = False
                    for child in self.tree.get_children():
                        if str(self.tree.item(child, "values")[1]) == str(cls_id): exists = True; break
                    if not exists:
                        self.tree.insert("", "end", values=("☐", cls_id, cls.get('maLopHocPhan'), cls.get('tenMonHoc'), tkb_str, status_text))
                        count_add += 1
                time.sleep(0.05)
            self.log(f"✅ Đã thêm {count_add} lớp.")
        except Exception as e: self.log(f"❌ Lỗi: {e}")
        self.reset_scan_btn()

    def reset_scan_btn(self):
        self.root.after(0, lambda: self.btn_scan.config(state="normal", text="🔎 QUÉT CHI TIẾT"))

    def on_tree_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell" and self.tree.identify_column(event.x) == "#1":
            item = self.tree.identify_row(event.y)
            if item:
                current_values = list(self.tree.item(item, "values"))
                current_state = current_values[0]
                subject_name = current_values[3]
                new_state = "☑" if current_state == "☐" else "☐"
                current_values[0] = new_state
                self.tree.item(item, values=current_values)
                if new_state == "☑":
                    for other_item in self.tree.get_children():
                        if other_item != item:
                            other_vals = list(self.tree.item(other_item, "values"))
                            if other_vals[3] == subject_name and other_vals[0] == "☑":
                                other_vals[0] = "☐"
                                self.tree.item(other_item, values=other_vals)
                self.update_spam_btn()

    def update_spam_btn(self):
        c = sum(1 for i in self.tree.get_children() if self.tree.item(i, "values")[0] == "☑")
        self.btn_spam.config(text=f"🚀 CHẠY SPAM ({c})")

    def clear_selection(self):
        for item in self.tree.get_children():
            if self.tree.item(item, "values")[0] == "☑": self.tree.delete(item)
        self.update_spam_btn()

    def toggle_spam(self):
        if not self.is_spamming:
            targets = []
            for item in self.tree.get_children():
                vals = self.tree.item(item, "values")
                if vals[0] == "☑":
                    targets.append({"id": vals[1], "name": vals[3], "row": item})
            if not targets: messagebox.showwarning("Trống", "Hãy tích chọn lớp!"); return
            self.is_spamming = True
            self.btn_spam.config(text="⏹ DỪNG SPAM")
            threading.Thread(target=self.spam_loop, args=(targets,)).start()
        else:
            self.is_spamming = False
            self.btn_spam.config(text="⏳ ĐANG DỪNG...")

    def spam_loop(self, targets):
        self.log(f"🔥 Bắt đầu Spam (Request Mới + Recaptcha)...")
        url = "https://portal.ut.edu.vn/api/v1/dkhp/dangKyLopHocPhan"
        
        while self.is_spamming and targets:
            next_round = []
            for t in targets:
                if not self.is_spamming: break
                try:
                    # --- THAY ĐỔI QUAN TRỌNG: Gửi Params trong URL, không dùng JSON body ---
                    params = {
                        "idLopHocPhan": str(t['id']),
                        "g-recaptcha-response": "" # Để trống, hy vọng server không check
                    }
                    
                    # Dùng params=params để requests tự ghép vào URL
                    resp = self.session.post(url, params=params, timeout=5)
                    
                    if resp.status_code == 200:
                        d = resp.json()
                        msg = d.get("message", "")
                        if d.get("success"):
                            self.log(f"🎉 THÀNH CÔNG: {t['name']}")
                            vals = list(self.tree.item(t['row'], "values"))
                            vals[0] = "✅"; vals[-1] = "ĐÃ ĐĂNG KÝ"
                            self.tree.item(t['row'], values=vals)
                        elif "đã đăng ký" in msg:
                            self.log(f"ℹ️ {t['name']}: Đã có.")
                            vals = list(self.tree.item(t['row'], "values"))
                            vals[0] = "✅"; vals[-1] = "TRÙNG"
                            self.tree.item(t['row'], values=vals)
                        else:
                            self.log(f"⚠️ {t['name']}: {msg}")
                            next_round.append(t)
                    elif resp.status_code == 401:
                        self.log("💀 Token hết hạn!"); self.is_spamming = False; break
                    else:
                        self.log(f"🔥 Lỗi HTTP {resp.status_code}")
                        next_round.append(t)
                except Exception as e:
                    self.log(f"❌ Lỗi mạng: {e}")
                    next_round.append(t)
                time.sleep(0.5) # Nghỉ lâu hơn chút để tránh bị chặn IP
            
            targets = next_round
            if self.is_spamming: time.sleep(1.5)

        self.root.after(0, lambda: self.btn_spam.config(text="🚀 TIẾP TỤC SPAM"))
        self.is_spamming = False

if __name__ == "__main__":
    root = tk.Tk()
    app = UTHRegisterApp(root)
    root.mainloop()