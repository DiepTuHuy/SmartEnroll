#!/usr/bin/env python3
"""Tài khoản của BẠN chạy SmartEnroll bản mới (đúng code core_state.py) chen vào cổng trường giả.

Đăng nhập lúc --start-at (giữa lúc đông nhất), vào được thì bật spam ngay; dừng lúc --end-at.
"""
import argparse
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, required=True)
ap.add_argument("--user", required=True)
ap.add_argument("--start-at", type=float, required=True)
ap.add_argument("--open-at", type=float, required=True)
ap.add_argument("--end-at", type=float, required=True)
ap.add_argument("--targets", default="1,16")
ap.add_argument("--mode", default="normal")
ap.add_argument("--out", required=True)
a = ap.parse_args()

tmp = tempfile.mkdtemp(prefix="smartenroll-me-")
os.environ["HOME"] = tmp
os.environ["USERPROFILE"] = tmp
os.chdir(tmp)
sys.path.insert(0, str(ROOT))
sys.stdout = open(os.devnull, "w")  # core_state prints every log line

import requests  # noqa: E402
from requests.adapters import HTTPAdapter  # noqa: E402
import core_state  # noqa: E402

base = f"http://127.0.0.1:{a.port}"


class ToFakePortal(HTTPAdapter):
    """Same settings as production; every portal URL goes to the local fake portal."""
    def send(self, request, *args, **kwargs):
        request.url = request.url.replace(core_state.PORTAL, base, 1)
        return super().send(request, *args, **kwargs)


def session_factory():
    s = requests.Session()
    adapter = ToFakePortal(pool_connections=20, pool_maxsize=64, max_retries=0)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


core_state._new_http_session = session_factory

time.sleep(max(0.0, a.start_at - time.time()))
st = core_state.AppState("me")
st.start_login_job(a.user, f"pw-{a.user}", persistent=True)
while st.login_job.get("status") == "running" and time.time() < a.end_at:
    time.sleep(0.05)
job = dict(st.login_job)
logged = job.get("status") == "success"
if logged:
    targets = [{"id": int(c), "name": f"lớp {c}"} for c in a.targets.split(",")]
    threading.Thread(target=st.run_spam_loop, args=(targets, a.mode), daemon=True).start()
    time.sleep(max(0.0, a.end_at - time.time()))
    st.is_spamming = False
else:
    st.stop_login_job()

with open(a.out, "w") as f:
    json.dump({
        "kind": f"tool-{a.mode}",
        "login_at": round(job["finished_at"] - a.open_at, 3) if logged else None,
        "login_attempts": job.get("attempts"),
        "stats": dict(st.stats),
        "log_tail": st.logs[-30:],
    }, f, ensure_ascii=False)
os._exit(0)  # don't wait for requests still in flight
