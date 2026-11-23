#!/usr/bin/env python3
"""Cổng trường GIẢ có giới hạn năng lực, chỉ dùng cho load test trên máy (không liên quan cổng thật).

Những điều QUAN SÁT ĐƯỢC trên cổng thật (11/2026, chỉ xem, không đăng ký gì) và được làm lại ở đây:
  - nginx đứng trước một backend kiểu Spring; HTTP/2; header `server: nginx`, `cache-control: no-cache, no-store...`
  - mọi API trả về cùng một vỏ JSON: {success, status, message, body, token, timestamp}
    (đăng nhập: token nằm ở trường `token`; các API khác: `token` = null, dữ liệu nằm trong `body`)
  - MỖI TÀI KHOẢN CHỈ CÓ 1 PHIÊN: đăng nhập ở nơi khác thì token cũ bị từ chối (401) ngay
    (thấy tận mắt: đăng nhập trên trình duyệt làm token của tool chết; tool đăng nhập lại thì trình duyệt bị đá ra)
  - đăng nhập và đăng ký đều gửi kèm `?g-recaptcha-response=...` trên URL (cổng không bắt buộc giá trị hợp lệ)
  - trang Đăng ký học phần gọi: getDot -> (chọn học kỳ) getLHPDaDangKy + getHocPhanHocMoi
    -> (chọn môn) getLopHocPhanChoDangKy -> (chọn lớp) getLopHocPhanDetail -> (bấm ĐĂNG KÝ) dangKyLopHocPhan
  - danh sách lớp không trả sĩ số mà trả `phanTramDangKy`, `choDangKy`, `isCanhBao`, `tenTrangThai`
  - lúc vắng: đăng nhập ~0.27s, các trang ~0.15-0.35s, danh sách lớp ~0.45s (nặng nhất)

Những điều GIẢ ĐỊNH (không quan sát được vì không được đăng ký / không có giờ cao điểm để xem):
  - năng lực xử lý (`--workers`), độ dài hàng chờ (`--max-queue`), thời gian chờ của nginx (`--gateway-timeout`)
  - request đã bị nginx trả 504 hoặc bị trình duyệt bỏ đi VẪN được backend xử lý sau đó ("request ma").
    Request đăng nhập ma vẫn cấp token mới, nên nó đá token đang dùng (vì chỉ có 1 phiên). Tắt bằng --no-zombies
  - nội dung lỗi 401 (dạng lỗi mặc định của Spring) và các câu thông báo khi đăng ký

Mô phỏng giờ cao điểm:
  - chỉ xử lý được `--workers` request cùng lúc; tối đa `--max-queue` request đứng chờ, quá thì trả 503 ngay
  - request chờ quá `--gateway-timeout` giây thì trả 504
  - hàng chờ kết nối TCP (`--backlog`) có hạn, nên khi bị dồn dập client gặp ConnectTimeout như thật
  - ngẫu nhiên ngắt kết nối giữa chừng, trả 502 dạng trang HTML, hủy token đang dùng (bắt đăng nhập lại)
  - lớp học có số chỗ giới hạn; trước giờ mở đăng ký thì trả lời "chưa đến thời gian"

Tài khoản hợp lệ: SV0001..SV{N}, mật khẩu "pw-SV0001"...
Xem số liệu: GET /__stats   (thêm ?detail=1 để có chi tiết từng tài khoản)
"""
import argparse
import asyncio
import base64
import collections
import datetime
import json
import logging
import random
import time

from aiohttp import web

try:
    import resource
except ImportError:  # Windows
    resource = None

NGINX_HEADERS = {
    "Server": "nginx",
    "Cache-Control": "no-cache, no-store, max-age=0, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


def _b64(obj):
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")


def envelope(body=None, message=None, success=True, status=200, token=None, http_status=200):
    """Vỏ JSON giống cổng thật."""
    return web.json_response({"success": success, "status": status, "message": message, "body": body,
                              "token": token, "timestamp": _now_iso()}, status=http_status)


def html_error(status, title):
    return web.Response(status=status, text=f"<html><head><title>{title}</title></head><body><center><h1>{title}</h1></center>"
                                            f"<hr><center>nginx</center></body></html>", content_type="text/html")


class Portal:
    def __init__(self, args):
        self.args = args
        self.rng = random.Random(args.seed)
        self.started = time.time()
        self.open_at = args.open_at if args.open_at else self.started + args.open_after
        self.sem = asyncio.Semaphore(args.workers)
        self.waiting = 0
        self.processing = 0
        self.max_waiting = 0
        self.max_processing = 0
        self.tokens = {}                      # live token -> username
        self.user_tokens = collections.defaultdict(list)  # username -> live tokens (1 when single-session)
        self.dead_tokens = {}                 # token killed by a newer login -> username
        self.token_seq = 0
        self.seats = {cid: args.seats for cid in range(1, args.classes + 1)}
        self.registered = {}                  # (username, class id) -> seconds after opening
        self.full_at = None
        self.class_order = collections.defaultdict(list)  # class id -> users in the order they got a seat
        self.counts = collections.Counter()   # "endpoint:outcome" -> n
        self.login_attempts = collections.Counter()
        self.first_login_at = {}              # username -> seconds after opening (negative = before)
        self.kicked = collections.Counter()   # username -> times a newer login killed this user's token
        self.zombie_logins = collections.Counter()  # username -> logins processed after the client had gone
        self.revoked = 0

    # ------------------------------------------------------------------ helpers
    def service_time(self, endpoint):
        a = self.args
        base = {"login": a.login_service, "dangKyLopHocPhan": a.register_service,
                "getLopHocPhanChoDangKy": a.list_service}
        low, spread = base.get(endpoint, a.page_service)
        return low + self.rng.random() * spread

    def new_token(self, username):
        self.token_seq += 1
        now = time.time()
        token = f"{_b64({'alg': 'HS256', 'typ': 'JWT'})}.{_b64({'sub': username, 'iat': now, 'exp': now + 30 * 86400, 'n': self.token_seq})}.sig{self.token_seq}"
        if not self.args.multi_session:
            # one session per account: every older token of this user stops working right now
            for old in self.user_tokens.pop(username, []):
                if self.tokens.pop(old, None) is not None:
                    self.dead_tokens[old] = username
                    self.kicked[username] += 1
        self.tokens[token] = username
        self.user_tokens[username].append(token)
        return token

    def bearer(self, request):
        return request.headers.get("Authorization", "").replace("Bearer ", "").strip()

    def unauthorized(self, request, endpoint):
        token = self.bearer(request)
        self.counts[f"{endpoint}:401" + ("-kicked" if token in self.dead_tokens else "")] += 1
        # Spring Security's default error body (an assumption: never saw the real one)
        return web.json_response({"timestamp": _now_iso(), "status": 401, "error": "Unauthorized",
                                  "path": request.path}, status=401)

    def subject_of(self, class_id):
        half = self.args.classes // 2
        return "0120000001" if class_id <= half else "0120000002"

    def classes_of(self, ma_hoc_phan):
        half = self.args.classes // 2
        if ma_hoc_phan == "0120000001":
            return range(1, half + 1)
        if ma_hoc_phan == "0120000002":
            return range(half + 1, self.args.classes + 1)
        return range(0)

    # ------------------------------------------------------------------ capacity + faults
    @web.middleware
    async def gate(self, request, handler):
        if request.path.startswith("/__"):
            return await handler(request)
        endpoint = request.path.rsplit("/", 1)[-1]
        roll = self.rng.random()
        if roll < self.args.reset_rate:
            self.counts[f"{endpoint}:reset"] += 1
            request.transport.close()          # client sees the connection drop mid-request
            raise web.HTTPServiceUnavailable()
        if self.waiting >= self.args.max_queue:
            self.counts[f"{endpoint}:503"] += 1
            return html_error(503, "503 Service Temporarily Unavailable")
        if roll < self.args.reset_rate + self.args.bad_gateway_rate:
            self.counts[f"{endpoint}:502"] += 1
            return html_error(502, "502 Bad Gateway")
        if request.can_read_body:
            await request.read()               # keep the body: the backend may handle it after the client is gone

        self.waiting += 1
        self.max_waiting = max(self.max_waiting, self.waiting)
        work = asyncio.ensure_future(self.backend(request, handler, endpoint))
        try:
            return await asyncio.wait_for(asyncio.shield(work), timeout=self.args.gateway_timeout)
        except asyncio.TimeoutError:
            self.counts[f"{endpoint}:504"] += 1
            if self.args.no_zombies:
                work.cancel()
            else:
                request["gateway_gave_up"] = True  # nginx answered 504, the backend still has the request
            return html_error(504, "504 Gateway Time-out")

    async def backend(self, request, handler, endpoint):
        try:
            await self.sem.acquire()
        except BaseException:
            self.waiting -= 1
            raise
        self.waiting -= 1
        self.processing += 1
        self.max_processing = max(self.max_processing, self.processing)
        try:
            await asyncio.sleep(self.service_time(endpoint))
            return await handler(request)
        finally:
            self.processing -= 1
            self.sem.release()

    def client_gone(self, request):
        transport = request.transport
        return request.get("gateway_gave_up") or transport is None or transport.is_closing()

    # ------------------------------------------------------------------ endpoints
    async def login(self, request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        username, password = body.get("username", ""), body.get("password", "")
        self.login_attempts[username] += 1
        if "g-recaptcha-response" not in request.query:
            self.counts["login:no-captcha-param"] += 1
        valid = username.startswith("SV") and username[2:].isdigit() and 1 <= int(username[2:]) <= self.args.accounts + self.args.extra_accounts
        if valid and password == f"pw-{username}":
            token = self.new_token(username)
            if self.client_gone(request):
                self.counts["login:ok-zombie"] += 1   # nobody receives this token, but it still kills the current one
                self.zombie_logins[username] += 1
            else:
                self.counts["login:ok"] += 1
                self.first_login_at.setdefault(username, round(time.time() - self.open_at, 3))
            response = envelope(token=token)
            response.set_cookie("ASP.NET_SessionId", f"s{self.token_seq}")
            return response
        self.counts["login:wrong-password"] += 1
        return envelope(success=False, message="Sai tài khoản hoặc mật khẩu")

    async def get_dot(self, request):
        if self.bearer(request) not in self.tokens:
            return self.unauthorized(request, "getDot")
        self.counts["getDot:ok"] += 1
        return envelope([
            {"id": 77, "tenHocKy": "Học kỳ 1 năm học 2026-2027", "isHanCheDot": False, "isHanCheThoiGian": False,
             "isDangKyHocPhan": True, "tuNgay": "08/09/2026 00:00", "denNgay": "12/09/2026 21:00"},
            {"id": 76, "tenHocKy": "Học kỳ hè năm học 2025-2026", "isHanCheDot": False, "isHanCheThoiGian": False,
             "isDangKyHocPhan": True, "tuNgay": None, "denNgay": None},
            {"id": 75, "tenHocKy": "Học kỳ 2 năm học 2025-2026", "isHanCheDot": True, "isHanCheThoiGian": False,
             "isDangKyHocPhan": False, "tuNgay": None, "denNgay": None},
        ])

    async def courses(self, request):
        """Danh sách môn chờ đăng ký (trang tải khi chọn học kỳ và mỗi lần F5)."""
        if self.bearer(request) not in self.tokens:
            return self.unauthorized(request, "getHocPhanHocMoi")
        self.counts["getHocPhanHocMoi:ok"] += 1
        return envelope([
            {"id": 4600 + i, "maHocPhan": f"012000000{i}", "tenHocPhan": f"Học phần giả {i}", "soTinChi": 3,
             "isBatBuoc": i == 1, "diemTongKet": None, "hocPhanTruoc": None, "tenHocPhanTruoc": None,
             "hocPhanTienQuyet": None, "tenHocPhanTienQuyet": None, "hocPhanSongHanh": None, "tenHocPhanSongHanh": None}
            for i in (1, 2)])

    async def class_list(self, request):
        """Danh sách lớp của 1 môn: chỉ có % đã đăng ký, không có sĩ số (giống cổng thật)."""
        if self.bearer(request) not in self.tokens:
            return self.unauthorized(request, "getLopHocPhanChoDangKy")
        self.counts["getLopHocPhanChoDangKy:ok"] += 1
        out = []
        for cid in self.classes_of(request.query.get("maHocPhan", "")):
            taken = self.args.seats - self.seats[cid]
            pct = round(100 * taken / self.args.seats) if self.args.seats else 100
            out.append({"id": cid, "maLopHocPhan": f"{self.subject_of(cid)}{cid:02d}", "tenMonHoc": f"Học phần giả {1 if cid <= self.args.classes // 2 else 2}",
                        "phanTramDangKy": pct, "isCanhBao": pct >= 80, "isHienPhanTram": False,
                        "choDangKy": True, "tenTrangThai": "Đã mở chính thức", "lopDuKien": None})
        return envelope(out)

    async def class_detail(self, request):
        if self.bearer(request) not in self.tokens:
            return self.unauthorized(request, "getLopHocPhanDetail")
        self.counts["getLopHocPhanDetail:ok"] += 1
        try:
            cid = int(request.query.get("idLopHocPhan", "0"))
        except ValueError:
            cid = 0
        # shape is an assumption (only the fields SmartEnroll reads are known to exist)
        return envelope([{"thu": 2 + cid % 6, "tietHoc": ["1-3", "4-6", "7-9", "10-12"][cid % 4], "phong": f"E{100 + cid}",
                          "tenGiangVien": "GV giả", "tuNgay": "14/09/2026", "denNgay": "20/12/2026"}])

    async def registered_list(self, request):
        user = self.tokens.get(self.bearer(request))
        if not user:
            return self.unauthorized(request, "getLHPDaDangKy")
        self.counts["getLHPDaDangKy:ok"] += 1
        mine = [cid for (u, cid) in self.registered if u == user]
        return envelope([{"id": 7000000 + cid, "maLopHocPhan": f"{self.subject_of(cid)}{cid:02d}", "tenMonHoc": "Học phần giả",
                          "soTinChi": 3, "lopDuKien": None, "mucHocPhi": 2940000, "daDongHocPhi": False,
                          "isAllowCancel": True, "tenTrangThaiDangKy": "Đăng ký mới", "tenTrangThaiLopHocPhan": "Đã mở chính thức",
                          "ngayDangKy": _now_iso(), "ngayHetHanNopHP": None} for cid in mine])

    async def register(self, request):
        token = self.bearer(request)
        user = self.tokens.get(token)
        if not user:
            return self.unauthorized(request, "dangKyLopHocPhan")
        if self.rng.random() < self.args.revoke_rate:
            # server-side logout of this session: the client must log in again
            self.tokens.pop(token, None)
            self.revoked += 1
            self.counts["dangKyLopHocPhan:revoked-401"] += 1
            return web.json_response({"timestamp": _now_iso(), "status": 401, "error": "Unauthorized", "path": request.path}, status=401)
        now = time.time()
        if now < self.open_at:
            self.counts["dangKyLopHocPhan:not-open"] += 1
            return envelope(success=False, message="Chưa đến thời gian đăng ký học phần")
        try:
            class_id = int(request.query.get("idLopHocPhan", "0"))
        except ValueError:
            class_id = 0
        if class_id not in self.seats:
            self.counts["dangKyLopHocPhan:bad-class"] += 1
            return envelope(success=False, message="Lớp học phần không tồn tại")
        if (user, class_id) in self.registered:
            self.counts["dangKyLopHocPhan:already"] += 1
            return envelope(success=False, message="Bạn đã đăng ký lớp học phần này rồi")
        if self.seats[class_id] <= 0:
            self.counts["dangKyLopHocPhan:full"] += 1
            return envelope(success=False, message="Lớp học phần đã đủ số lượng sinh viên")
        self.seats[class_id] -= 1
        self.registered[(user, class_id)] = round(now - self.open_at, 3)
        self.class_order[class_id].append(user)
        if self.full_at is None and all(left == 0 for left in self.seats.values()):
            self.full_at = now
        self.counts["dangKyLopHocPhan:ok" + ("-zombie" if self.client_gone(request) else "")] += 1
        return envelope(message="Đăng ký thành công")

    async def stats(self, request):
        now = time.time()
        data = {
            "uptime": round(now - self.started, 2),
            "open_in": round(self.open_at - now, 3),
            "waiting": self.waiting,
            "processing": self.processing,
            "max_waiting": self.max_waiting,
            "max_processing": self.max_processing,
            "counts": dict(self.counts),
            "requests_total": sum(self.counts.values()),
            "seats_total": self.args.classes * self.args.seats,
            "seats_left": sum(self.seats.values()),
            "registrations": len(self.registered),
            "full_after_open": round(self.full_at - self.open_at, 3) if self.full_at else None,
            "revoked": self.revoked,
            "kicked_total": sum(self.kicked.values()),
            "zombie_logins_total": sum(self.zombie_logins.values()),
        }
        if request.query.get("detail"):
            per_user = collections.defaultdict(list)
            for (user, class_id), at in self.registered.items():
                per_user[user].append({"class": class_id, "at": at, "rank": self.class_order[class_id].index(user) + 1})
            data["per_user"] = per_user
            data["login_attempts"] = dict(self.login_attempts)
            data["first_login_at"] = self.first_login_at
            data["kicked"] = dict(self.kicked)
            data["zombie_logins"] = dict(self.zombie_logins)
        return web.json_response(data)


async def _nginx_headers(request, response):
    if not request.path.startswith("/__"):
        for k, v in NGINX_HEADERS.items():
            response.headers[k] = v


async def main(args):
    logging.getLogger("aiohttp").setLevel(logging.CRITICAL)
    portal = Portal(args)
    app = web.Application(middlewares=[portal.gate])
    app.on_response_prepare.append(_nginx_headers)
    app.router.add_post("/api/v1/user/login", portal.login)
    app.router.add_get("/api/v1/dkhp/getDot", portal.get_dot)
    app.router.add_get("/api/v1/dkhp/getHocPhanHocMoi", portal.courses)
    app.router.add_get("/api/v1/dkhp/getLopHocPhanChoDangKy", portal.class_list)
    app.router.add_get("/api/v1/dkhp/getLopHocPhanDetail", portal.class_detail)
    app.router.add_get("/api/v1/dkhp/getLHPDaDangKy", portal.registered_list)
    app.router.add_post("/api/v1/dkhp/dangKyLopHocPhan", portal.register)
    app.router.add_get("/__stats", portal.stats)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", args.port, backlog=args.backlog).start()
    print(f"fake portal on :{args.port} | workers={args.workers} queue={args.max_queue} gateway={args.gateway_timeout}s backlog={args.backlog} "
          f"| {args.classes} classes x {args.seats} seats | opens in {round(portal.open_at - time.time(), 1)}s "
          f"| {'multi' if args.multi_session else 'single'}-session, zombies {'off' if args.no_zombies else 'on'}", flush=True)
    await asyncio.Event().wait()


def _pair(v):
    return tuple(map(float, v.split(",")))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5099)
    parser.add_argument("--accounts", type=int, default=1000)
    parser.add_argument("--open-after", type=float, default=45)
    parser.add_argument("--open-at", type=float, default=0, help="absolute epoch time registration opens (overrides --open-after)")
    parser.add_argument("--extra-accounts", type=int, default=10, help="valid accounts beyond --accounts (for observers)")
    parser.add_argument("--gateway-timeout", type=float, default=60, help="seconds a request may wait in line before 504")
    parser.add_argument("--login-service", type=_pair, default=(0.25, 0.25), help="login processing time: min,spread seconds")
    parser.add_argument("--register-service", type=_pair, default=(0.04, 0.08))
    parser.add_argument("--page-service", type=_pair, default=(0.02, 0.03))
    parser.add_argument("--list-service", type=_pair, default=(0.06, 0.09), help="getLopHocPhanChoDangKy (the heaviest page)")
    parser.add_argument("--workers", type=int, default=60, help="requests processed at the same time")
    parser.add_argument("--max-queue", type=int, default=600, help="waiting requests before answering 503")
    parser.add_argument("--backlog", type=int, default=128, help="TCP accept queue")
    parser.add_argument("--classes", type=int, default=30)
    parser.add_argument("--seats", type=int, default=30)
    parser.add_argument("--reset-rate", type=float, default=0.01)
    parser.add_argument("--bad-gateway-rate", type=float, default=0.01)
    parser.add_argument("--revoke-rate", type=float, default=0.002)
    parser.add_argument("--multi-session", action="store_true", help="allow several live tokens per account (the real portal does NOT)")
    parser.add_argument("--no-zombies", action="store_true", help="drop requests nginx gave up on instead of still processing them")
    parser.add_argument("--seed", type=int, default=7)
    cli = parser.parse_args()
    if resource is not None:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        target = 65536 if hard == resource.RLIM_INFINITY else min(hard, 65536)
        if soft < target:
            resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))
    asyncio.run(main(cli))
