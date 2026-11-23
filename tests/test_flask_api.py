"""Các API đăng nhập nền / trạng thái / cấu hình thủ công / đăng xuất của server.py.

Chạy:  venv/bin/python tests/test_flask_api.py
Không có mạng thật: mọi request tới cổng trường đi vào cổng giả trong tests/fakes.py.
"""
from fakes import *  # noqa: F401,F403  (phải import đầu tiên: cô lập HOME, thay HTTP bằng cổng giả)
from fakes import PORTAL, check, finish, jwt, wait_for, wait_quiet, write_cfg, core_state
import threading
import time
import json
import os

import server

c = server.app.test_client()
PORTAL.script("login", "connect_timeout", 502, "ok")
PORTAL.script("getDot", "ok")

r = c.get("/api/config")
check(r.status_code == 200 and r.json["exists"] is False, "no saved config at start")
r = c.post("/api/config/login", json={"username": "u1", "password": ""})
check(r.status_code == 400, "missing password -> 400")
r = c.post("/api/config/login", json={"username": "u1", "password": "pw", "persistent": True})
check(r.status_code == 202 and r.json.get("started"), "login job starts and returns immediately (202)")
check(wait_for(lambda: c.get("/api/config/login/status").json["status"] != "running", 10), "login job finishes")
s = c.get("/api/config/login/status").json
check(s["status"] == "success" and s["attempts"] == 3 and s.get("config"), "login got through a timeout and a 502 on the 3rd try")
r = c.get("/api/config")
check(r.json["exists"] and r.json["token_expires_at"] > time.time(), "config saved with token expiry")
r = c.post("/api/config/manual", json={"token": "abc", "username": "u1", "password": "pw"})
check(r.status_code == 200, "manual config saves")
# the portal's own reason must reach the user (it used to be just "Portal trả về mã 403")
PORTAL.script("getHocPhanHocMoi", (403, {"message": "Ngoài thời gian đăng ký học phần"}))
r = c.get("/api/courses?type=new&idDot=77")
check(r.status_code == 403 and "Ngoài thời gian đăng ký học phần" in r.json["message"], "403 shows the portal's own reason")
PORTAL.script("getHocPhanHocMoi", 403)
r = c.get("/api/courses?type=new&idDot=77")
check(r.status_code == 403 and "từ chối truy cập" in r.json["message"], "403 without a reason gets a plain-language hint")
print("   ->", r.json["message"])
r = c.post("/api/config/logout")
check(r.status_code == 200, "logout works")
check(c.get("/api/config").json["exists"] is False, "logout sticks (no stale config copied back)")

finish()
