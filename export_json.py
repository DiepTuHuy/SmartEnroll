import asyncio
import json
import os
from core_state import AppState

async def build_export_data(dkhp_state):
    # 1. & 2. Get grades
    bangdiem_url = "https://portal.ut.edu.vn/api/v1/hoctap/bangdiem2"
    r = await asyncio.to_thread(dkhp_state.request_with_retry, "GET", bangdiem_url, timeout=10)
    
    bangdiem_data = []
    if r.status_code == 200:
        bangdiem_data = r.json().get("data") or r.json().get("body") or []
        
    # Get dots
    dot_url = "https://portal.ut.edu.vn/api/v1/dkhp/getDot"
    r_dot = await asyncio.to_thread(dkhp_state.request_with_retry, "GET", dot_url, timeout=5)
    dots = []
    if r_dot.status_code == 200:
        dots = r_dot.json().get("data") or r_dot.json().get("body") or []
    
    da_dang_ky_all = []
    chua_dang_ky = []
    dang_dang_ky_chua_hoc = []
    
    # 3. Get all historically registered courses (các môn đã đăng ký)
    # We will fetch for the latest dot, and maybe all active dots
    latest_dot_id = dots[0]['id'] if dots else None
    
    if latest_dot_id:
        # Get registered for current dot
        r_reg = await asyncio.to_thread(dkhp_state.request_with_retry, "GET", "https://portal.ut.edu.vn/api/v1/dkhp/getLHPDaDangKy", params={"idDot": latest_dot_id}, timeout=5)
        if r_reg.status_code == 200:
            reg_data = r_reg.json().get("data") or r_reg.json().get("body") or []
            for c in reg_data:
                da_dang_ky_all.append({
                    "maHocPhan": c.get("maHocPhan", ""),
                    "tenMonHoc": c.get("tenMonHoc", ""),
                    "soTinChi": c.get("soTinChi", 0),
                    "lopDuKien": c.get("lopDuKien", "")
                })
                # If they are registered in the latest dot, they are "chưa học" (haven't studied yet)
                dang_dang_ky_chua_hoc.append({
                    "maHocPhan": c.get("maHocPhan", ""),
                    "tenMonHoc": c.get("tenMonHoc", ""),
                    "soTinChi": c.get("soTinChi", 0)
                })
        
        # 4. Get available courses (chưa đăng ký)
        r_moi = await asyncio.to_thread(dkhp_state.request_with_retry, "GET", "https://portal.ut.edu.vn/api/v1/dkhp/getHocPhanHocMoi", params={"idDot": latest_dot_id}, timeout=5)
        if r_moi.status_code == 200:
            moi_data = r_moi.json().get("data") or r_moi.json().get("body") or []
            registered_ma_hp = [c["maHocPhan"] for c in da_dang_ky_all]
            
            for m in moi_data:
                if m.get("maHocPhan") not in registered_ma_hp:
                    chua_dang_ky.append({
                        "maHocPhan": m.get("maHocPhan", ""),
                        "tenMonHoc": m.get("tenHocPhan", ""),
                        "soTinChi": m.get("soTinChi", 0),
                        "isBatBuoc": m.get("isBatBuoc", False)
                    })
                    
    # Historical registered can also be derived from bangdiem2!
    for dot in bangdiem_data:
        for diem in dot.get("diems", []):
            da_dang_ky_all.append({
                "maHocPhan": diem.get("maLopHocPhan", ""),
                "tenMonHoc": diem.get("tenMonHoc", ""),
                "soTinChi": diem.get("soTinChi", 0),
                "dot": dot.get("tenDot", "")
            })
            
    # Deduplicate da_dang_ky_all by maHocPhan
    seen = set()
    da_dang_ky_unique = []
    for c in da_dang_ky_all:
        if c["maHocPhan"] not in seen:
            seen.add(c["maHocPhan"])
            da_dang_ky_unique.append(c)

    # Fetch chuong trinh khung
    chuongtrinhkhung_url = "https://portal.ut.edu.vn/api/v1/hoctap/chuongtrinhkhung"
    r_ctk = await asyncio.to_thread(dkhp_state.request_with_retry, "GET", chuongtrinhkhung_url, timeout=10)
    chuongtrinhkhung_data = []
    if r_ctk.status_code == 200:
        chuongtrinhkhung_data = r_ctk.json().get("data") or r_ctk.json().get("body") or []

    export_json = {
        "thongTinSinhVien": {
            "mssv": dkhp_state.config.get("username")
        },
        "diemTatCaHocKy": bangdiem_data,
        "monDaDangKy": da_dang_ky_unique,
        "monChuaDangKy": chua_dang_ky,
        "monDangDangKyChuaHoc": dang_dang_ky_chua_hoc,
        "chuongTrinhKhung": chuongtrinhkhung_data
    }
    
    return export_json

if __name__ == "__main__":
    async def main():
        from core_state import get_app_state
        state = get_app_state("web_default")
        import json
        with open(os.path.expanduser("~/.smartenroll_config.json")) as f:
            config = json.load(f)
        state.login_with_credentials(config['username'], config['password'])
        data = await build_export_data(state)
        with open("export_test.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print("Export successful!")
        print("Keys in JSON:", list(data.keys()))
        
    asyncio.run(main())
