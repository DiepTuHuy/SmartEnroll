"""Đăng nhập & spam đăng ký khi cổng trường quá tải (timeout, 502/503, trang HTML, token hết hạn...).

Chạy:  venv/bin/python tests/test_overload.py
Không có mạng thật: mọi request tới cổng trường đi vào cổng giả trong tests/fakes.py.
"""
from fakes import *  # noqa: F401,F403  (phải import đầu tiên: cô lập HOME, thay HTTP bằng cổng giả)
from fakes import PORTAL, check, finish, jwt, wait_for, wait_quiet, write_cfg, core_state
import threading
import time
import json
import os

# ---------------------------------------------------------------- 1. startup never blocks on the portal
PORTAL.script("getDot", "slow")
write_cfg("t1", jwt(30 * 86400, "old"))
t0 = time.time()
st = core_state.AppState("t1")
check(time.time() - t0 < 1.0, f"AppState() returns immediately even when portal is slow ({time.time()-t0:.2f}s)")
check(st.config["token"].endswith(".sig"), "saved config loaded")
check(st.token_expires_at() is not None and st.token_expires_at() > time.time(), "JWT expiry decoded")

# ---------------------------------------------------------------- 2. persistent login survives overload, old token untouched meanwhile
PORTAL.script("getDot", "ok")
old_auth = st.session.headers["Authorization"]
PORTAL.script("login", "connect_timeout", "connect_timeout", "read_timeout", 503, 502, "html200", "reset", "ok")
ok, info = st.start_login_job("2251010000", "pw", persistent=True)
check(ok and info == "started", "login job started")
saw_old_token_during_retries = []
def watch():
    while st.login_job["status"] == "running":
        saw_old_token_during_retries.append(st.session.headers.get("Authorization") == old_auth or st.login_job["status"] != "running")
        time.sleep(0.05)
threading.Thread(target=watch, daemon=True).start()
check(wait_for(lambda: st.login_job["status"] != "running", 30), "login job finished")
check(st.login_job["status"] == "success", f"login succeeded after overload (status={st.login_job['status']}, attempts={st.login_job['attempts']})")
check(st.login_job["attempts"] == 8, "took exactly 8 attempts (7 failures + success)")
check(all(saw_old_token_during_retries), "old token stayed in session while retries were failing")
check(st.session.headers["Authorization"] != old_auth, "new token swapped in after success")
check(json.load(open(st.config_file))["token"] == st.config["token"], "new token persisted to disk")
check(wait_for(lambda: st.config.get("id_dot") == "99", 5), "latest id_dot refreshed in background")
check(not os.path.exists(st.config_file + ".tmp"), "no leftover temp file")

# ---------------------------------------------------------------- 3. wrong password stops immediately
PORTAL.calls["login"] = 0
PORTAL.script("login", "Sai tài khoản hoặc mật khẩu")
token_before = st.config["token"]
st.start_login_job("2251010000", "bad", persistent=True)
check(wait_for(lambda: st.login_job["status"] != "running", 5), "wrong-password job ends")
check(st.login_job["status"] == "failed" and PORTAL.calls["login"] == 1, f"wrong password -> fail after 1 attempt (calls={PORTAL.calls['login']})")
check(st.config["token"] == token_before, "failed login did not touch the working token")

# ---------------------------------------------------------------- 4. unknown rejection repeated -> stop after cap
PORTAL.calls["login"] = 0
PORTAL.script("login", "Mã xác thực không hợp lệ")
core_state._backoff = lambda *a, **k: 0.01  # speed
st.start_login_job("2251010000", "pw", persistent=True)
check(wait_for(lambda: st.login_job["status"] != "running", 10), "unknown-rejection job ends")
check(st.login_job["status"] == "failed" and PORTAL.calls["login"] == core_state.MAX_IDENTICAL_LOGIN_REJECTIONS,
      f"identical rejection capped at {core_state.MAX_IDENTICAL_LOGIN_REJECTIONS} (calls={PORTAL.calls['login']})")

# ---------------------------------------------------------------- 5. stop button
PORTAL.script("login", "connect_timeout")
st.start_login_job("2251010000", "pw", persistent=True)
time.sleep(1.0)
st.stop_login_job()
check(st.login_job["status"] == "stopped", "stop -> status stopped immediately")
time.sleep(1.5)
n = PORTAL.calls["login"]
time.sleep(1.0)
check(PORTAL.calls["login"] == n, "no more login attempts after stop")

# ---------------------------------------------------------------- 6. request_with_retry: 503 x2 then OK
PORTAL.script("getSomething", 503, 503, "ok")
resp = st.request_with_retry("GET", "https://portal.ut.edu.vn/api/v1/x/getSomething", timeout=5)
check(resp.status_code == 200, "GET retried through two 503s")

# ---------------------------------------------------------------- 7. turbo spam: overload + expired token mid-run, single-flight relogin
PORTAL.calls = {}
PORTAL.auth_seen = []
PORTAL.valid_tokens = set()          # current token becomes invalid -> 401 on check_token
PORTAL.script("login", "connect_timeout", 503, "ok")
PORTAL.script("reg:1", "Lớp học phần đã đủ số lượng", "Lớp học phần đã đủ số lượng", 502, "read_timeout", "reset", "check_token")
PORTAL.script("reg:2", "check_token")
targets = [{"id": 1, "name": "Toán"}, {"id": 2, "name": "Lý"}]
t0 = time.time()
th = threading.Thread(target=st.run_spam_loop, args=(targets, "turbo"), daemon=True)
th.start()
th.join(40)
check(not th.is_alive(), f"turbo campaign finished ({time.time()-t0:.1f}s)")
check(st.is_spamming is False, "is_spamming reset")
check(st.stats["success_count"] == 2, f"both classes registered (stats={st.stats})")
check(PORTAL.calls.get("login") == 3, f"exactly one relogin sequence for all lanes (login calls={PORTAL.calls.get('login')})")
check(st.stats.get("relogins", 0) >= 1, "relogin counted")
check(any("ĐĂNG KÝ THÀNH CÔNG: Toán" in l for l in st.logs) and any("ĐĂNG KÝ THÀNH CÔNG: Lý" in l for l in st.logs), "success logged for both")
check(PORTAL.calls.get("getDot", 0) == 0, "re-login during spam sends no extra period refresh (less load at peak time)")

# ---------------------------------------------------------------- 8. stop during a never-ending campaign returns fast
PORTAL.script("reg:3", "Chưa đến thời gian đăng ký")
th = threading.Thread(target=st.run_spam_loop, args=([{"id": 3, "name": "Hóa"}], "normal"), daemon=True)
th.start()
time.sleep(2.5)
reqs_before = st.stats["total_requests"]
st.is_spamming = False
th.join(3)
check(not th.is_alive(), "campaign thread exits within 3s of stop")
check(1 <= reqs_before <= 4, f"normal mode paces ~1 req/s per class ({reqs_before} in 2.5s)")
dedup_lines = [l for l in st.logs if "Chưa đến thời gian" in l]
check(len(dedup_lines) == 1, f"repeated rejection logged once, not every time ({len(dedup_lines)} lines)")

# ---------------------------------------------------------------- 9. a restarted campaign is not killed by the old one finishing
PORTAL.script("reg:4", "read_timeout")
PORTAL.script("reg:5", "Lớp đầy")
th_old = threading.Thread(target=st.run_spam_loop, args=([{"id": 4, "name": "A"}], "normal"), daemon=True)
th_old.start(); time.sleep(0.5)
st.is_spamming = False; th_old.join(3)
th_new = threading.Thread(target=st.run_spam_loop, args=([{"id": 5, "name": "B"}], "normal"), daemon=True)
th_new.start(); time.sleep(1.5)
check(st.is_spamming, "new campaign still running after old one wound down")
st.is_spamming = False; th_new.join(3)

# ---------------------------------------------------------------- 10. 401 without saved password stops campaign with clear message
write_cfg("t2", jwt(30 * 86400, "x"), with_creds=False)
st2 = core_state.AppState("t2")
PORTAL.script("reg:6", "expired")
th = threading.Thread(target=st2.run_spam_loop, args=([{"id": 6, "name": "C"}], "normal"), daemon=True)
th.start(); th.join(5)
check(not th.is_alive() and not st2.is_spamming, "no-credentials 401 stops campaign")
check(any("Không tự đăng nhập lại được" in l for l in st2.logs), "clear message logged")

# ---------------------------------------------------------------- 11. expired saved JWT -> background relogin at startup
PORTAL.calls = {}
PORTAL.script("login", "ok")
write_cfg("t3", jwt(-10, "expired"))
st3 = core_state.AppState("t3")
check(wait_for(lambda: PORTAL.calls.get("login") == 1, 5), "expired saved token triggers one background relogin")
check(wait_for(lambda: (st3.token_expires_at() or 0) > time.time(), 3), "fresh token in place")

finish()
