"""Hạ tầng test dùng chung: cổng trường GIẢ chạy ngay trong tiến trình (không có mạng thật).

Import module này TRƯỚC mọi thứ khác trong một file test. Nó sẽ:
  - trỏ HOME/USERPROFILE sang một thư mục tạm, nên file cấu hình thật của bạn không bao giờ bị đụng tới
  - chuyển thư mục làm việc sang thư mục tạm (tránh việc tự chép config.json cũ của dự án)
  - thay mọi kết nối HTTP của core_state bằng FakeAdapter bên dưới
"""
import base64
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent.parent
_TMP_HOME = tempfile.mkdtemp(prefix="smartenroll-test-")
os.environ["HOME"] = _TMP_HOME
os.environ["USERPROFILE"] = _TMP_HOME
os.chdir(_TMP_HOME)
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402
from requests.adapters import BaseAdapter  # noqa: E402
from requests.structures import CaseInsensitiveDict  # noqa: E402

import core_state  # noqa: E402

FAILS = []


def check(cond, label):
    print(("PASS " if cond else "FAIL ") + label, flush=True)
    if not cond:
        FAILS.append(label)


def finish():
    print()
    print("ALL PASSED" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}")
    sys.exit(1 if FAILS else 0)


def jwt(exp_offset, tag):
    head = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps({"exp": time.time() + exp_offset, "iat": time.time(), "sub": tag}).encode()).rstrip(b"=").decode()
    return f"{head}.{body}.sig"


def make_response(req, status, body=None, text=None, headers=None, cookies=None):
    r = requests.Response()
    r.status_code = status
    r.request = req
    r.url = req.url
    r.headers = CaseInsensitiveDict(headers or {})
    if body is not None:
        r._content = json.dumps(body).encode()
        r.headers["Content-Type"] = "application/json"
    else:
        r._content = (text or "").encode()
        r.headers.setdefault("Content-Type", "text/html")
    r.encoding = "utf-8"
    for k, v in (cookies or {}).items():
        r.headers["Set-Cookie"] = f"{k}={v}; Path=/"
    return r


class FakePortal:
    """Kịch bản cho từng endpoint: mỗi lần gọi lấy hành vi kế tiếp trong hàng; hành vi cuối được lặp lại.

    Hành vi: "ok", "connect_timeout", "read_timeout", "reset", "html200", số HTTP (503...),
    (mã HTTP, JSON) tùy ý, chuỗi thông báo từ chối, hoặc hàm nhận request và trả về một trong các giá trị trên.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.queues = {}
        self.calls = {}
        self.auth_seen = []
        self.valid_tokens = set()

    def script(self, key, *behaviours):
        self.queues[key] = list(behaviours)

    def next(self, key):
        with self.lock:
            self.calls[key] = self.calls.get(key, 0) + 1
            q = self.queues.get(key) or ["ok"]
            return q.pop(0) if len(q) > 1 else q[0]

    def total_calls(self):
        with self.lock:
            return sum(self.calls.values())


PORTAL = FakePortal()


class FakeAdapter(BaseAdapter):
    def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        path = urlparse(request.url).path
        q = parse_qs(urlparse(request.url).query)
        key = path.rsplit("/", 1)[-1]
        auth = request.headers.get("Authorization", "")
        if key == "login":
            b = PORTAL.next("login")
        elif key == "dangKyLopHocPhan":
            PORTAL.auth_seen.append(auth)
            b = PORTAL.next("reg:" + q["idLopHocPhan"][0])
        else:
            b = PORTAL.next(key)

        if callable(b):
            b = b(request)
        if isinstance(b, tuple):  # (status, json body): any custom answer
            return make_response(request, b[0], b[1])
        if b == "connect_timeout":
            raise requests.exceptions.ConnectTimeout("simulated SYN drop")
        if b == "read_timeout":
            raise requests.exceptions.ReadTimeout("simulated slow backend")
        if b == "reset":
            raise requests.exceptions.ConnectionError("simulated reset")
        if isinstance(b, int):
            return make_response(request, b, text="<html>busy</html>")
        if b == "html200":
            return make_response(request, 200, text="<html>Hệ thống đang xử lý</html>")
        if key == "login":
            if b == "ok":
                token = jwt(30 * 86400, "new%d" % PORTAL.calls["login"])
                PORTAL.valid_tokens.add(token)
                return make_response(request, 200, {"success": True, "token": token}, cookies={"ASP.NET_SessionId": "abc"})
            return make_response(request, 200, {"success": False, "message": b})
        if key == "dangKyLopHocPhan":
            token = auth.replace("Bearer ", "")
            if b == "check_token":
                if token not in PORTAL.valid_tokens:
                    return make_response(request, 401, {"message": "Unauthorized"})
                b = "ok"
            if b == "ok":
                return make_response(request, 200, {"success": True, "message": "Đăng ký thành công"})
            if b == "expired":
                return make_response(request, 401, {"message": "Unauthorized"})
            return make_response(request, 200, {"success": False, "message": b})
        if key == "getDot":
            if b == "slow":
                time.sleep(4)
                b = "ok"
            if b == "unauth":
                return make_response(request, 401, {"message": "Unauthorized"})
            return make_response(request, 200, {"data": [{"id": 99}]})
        if key == "getSomething":
            return make_response(request, 200, {"data": []})
        return make_response(request, 404, text="nf")

    def close(self):
        pass


def fake_session():
    s = requests.Session()
    s.mount("https://", FakeAdapter())
    s.mount("http://", FakeAdapter())
    return s


core_state._new_http_session = fake_session


def write_cfg(name, token, with_creds=True):
    cfg = {"token": token, "cookie": "", "id_dot": "75", "user_agent": "UA"}
    if with_creds:
        cfg.update(username="2251010000", password="pw")
    path = os.path.join(os.path.expanduser("~"), f".smartenroll_config_{name}.json")
    with open(path, "w") as f:
        json.dump(cfg, f)


def wait_for(pred, timeout):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.05)
    return pred()


def wait_quiet(quiet=1.0, timeout=15):
    """Chờ tới khi cổng giả không nhận thêm request nào trong `quiet` giây (việc nền đã chạy xong)."""
    end = time.time() + timeout
    last, since = PORTAL.total_calls(), time.time()
    while time.time() < end:
        time.sleep(0.05)
        now_calls = PORTAL.total_calls()
        if now_calls != last:
            last, since = now_calls, time.time()
        elif time.time() - since >= quiet:
            return True
    return False
