#!/usr/bin/env python3
"""Cổng trường GIẢ có giới hạn năng lực, chỉ dùng cho load test trên máy (không liên quan cổng thật).

Mô phỏng giờ cao điểm:
  - chỉ xử lý được `--workers` request cùng lúc; tối đa `--max-queue` request đứng chờ, quá thì trả 503 ngay
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
import json
import logging
import random
import time

from aiohttp import web

try:
    import resource
except ImportError:  # Windows
    resource = None


def _b64(obj):
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


class Portal:
    def __init__(self, args):
        self.args = args
        self.rng = random.Random(args.seed)
        self.started = time.time()
        self.open_at = self.started + args.open_after
        self.sem = asyncio.Semaphore(args.workers)
        self.waiting = 0
        self.processing = 0
        self.max_waiting = 0
        self.max_processing = 0
        self.tokens = {}                      # token -> username
        self.token_seq = 0
        self.seats = {cid: args.seats for cid in range(1, args.classes + 1)}
        self.registered = {}                  # (username, class id) -> seconds after opening
        self.full_at = None
        self.counts = collections.Counter()   # "endpoint:outcome" -> n
        self.login_attempts = collections.Counter()
        self.revoked = 0

    # ------------------------------------------------------------------ helpers
    def service_time(self, endpoint):
        base = {"login": (0.25, 0.25), "dangKyLopHocPhan": (0.04, 0.08), "getDot": (0.02, 0.03)}
        low, spread = base.get(endpoint, (0.02, 0.03))
        return low + self.rng.random() * spread

    def new_token(self, username):
        self.token_seq += 1
        now = time.time()
        token = f"{_b64({'alg': 'HS256', 'typ': 'JWT'})}.{_b64({'sub': username, 'iat': now, 'exp': now + 30 * 86400, 'n': self.token_seq})}.sig{self.token_seq}"
        self.tokens[token] = username
        return token

    def user_of(self, request):
        auth = request.headers.get("Authorization", "")
        return self.tokens.get(auth.replace("Bearer ", "").strip())

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
            return web.Response(status=503, text="<html>503 Service Temporarily Unavailable</html>", content_type="text/html")
        if roll < self.args.reset_rate + self.args.bad_gateway_rate:
            self.counts[f"{endpoint}:502"] += 1
            return web.Response(status=502, text="<html>502 Bad Gateway</html>", content_type="text/html")

        self.waiting += 1
        self.max_waiting = max(self.max_waiting, self.waiting)
        queued = True
        try:
            async with self.sem:
                self.waiting -= 1
                queued = False
                self.processing += 1
                self.max_processing = max(self.max_processing, self.processing)
                try:
                    await asyncio.sleep(self.service_time(endpoint))
                    return await handler(request)
                finally:
                    self.processing -= 1
        finally:
            if queued:  # client gave up while waiting in line
                self.waiting -= 1

    # ------------------------------------------------------------------ endpoints
    async def login(self, request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        username, password = body.get("username", ""), body.get("password", "")
        self.login_attempts[username] += 1
        valid = username.startswith("SV") and username[2:].isdigit() and 1 <= int(username[2:]) <= self.args.accounts
        if valid and password == f"pw-{username}":
            self.counts["login:ok"] += 1
            response = web.json_response({"success": True, "token": self.new_token(username)})
            response.set_cookie("ASP.NET_SessionId", f"s{self.token_seq}")
            return response
        self.counts["login:wrong-password"] += 1
        return web.json_response({"success": False, "message": "Sai tài khoản hoặc mật khẩu"})

    async def get_dot(self, request):
        if not self.user_of(request):
            self.counts["getDot:401"] += 1
            return web.json_response({"message": "Unauthorized"}, status=401)
        self.counts["getDot:ok"] += 1
        return web.json_response({"data": [{"id": 77, "tenHocKy": "HK2 2026-2027"}]})

    async def register(self, request):
        user = self.user_of(request)
        if not user:
            self.counts["dangKyLopHocPhan:401"] += 1
            return web.json_response({"message": "Unauthorized"}, status=401)
        if self.rng.random() < self.args.revoke_rate:
            # server-side logout of this session: the client must log in again
            self.tokens.pop(request.headers.get("Authorization", "").replace("Bearer ", "").strip(), None)
            self.revoked += 1
            self.counts["dangKyLopHocPhan:revoked-401"] += 1
            return web.json_response({"message": "Unauthorized"}, status=401)
        now = time.time()
        if now < self.open_at:
            self.counts["dangKyLopHocPhan:not-open"] += 1
            return web.json_response({"success": False, "message": "Chưa đến thời gian đăng ký học phần"})
        try:
            class_id = int(request.query.get("idLopHocPhan", "0"))
        except ValueError:
            class_id = 0
        if class_id not in self.seats:
            self.counts["dangKyLopHocPhan:bad-class"] += 1
            return web.json_response({"success": False, "message": "Lớp học phần không tồn tại"})
        if (user, class_id) in self.registered:
            self.counts["dangKyLopHocPhan:already"] += 1
            return web.json_response({"success": False, "message": "Bạn đã đăng ký lớp học phần này rồi"})
        if self.seats[class_id] <= 0:
            self.counts["dangKyLopHocPhan:full"] += 1
            return web.json_response({"success": False, "message": "Lớp học phần đã đủ số lượng sinh viên"})
        self.seats[class_id] -= 1
        self.registered[(user, class_id)] = round(now - self.open_at, 3)
        if self.full_at is None and all(left == 0 for left in self.seats.values()):
            self.full_at = now
        self.counts["dangKyLopHocPhan:ok"] += 1
        return web.json_response({"success": True, "message": "Đăng ký thành công"})

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
        }
        if request.query.get("detail"):
            per_user = collections.defaultdict(list)
            for (user, class_id), at in self.registered.items():
                per_user[user].append({"class": class_id, "at": at})
            data["per_user"] = per_user
            data["login_attempts"] = dict(self.login_attempts)
        return web.json_response(data)


async def main(args):
    logging.getLogger("aiohttp").setLevel(logging.CRITICAL)
    portal = Portal(args)
    app = web.Application(middlewares=[portal.gate])
    app.router.add_post("/api/v1/user/login", portal.login)
    app.router.add_get("/api/v1/dkhp/getDot", portal.get_dot)
    app.router.add_post("/api/v1/dkhp/dangKyLopHocPhan", portal.register)
    app.router.add_get("/__stats", portal.stats)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", args.port, backlog=args.backlog).start()
    print(f"fake portal on :{args.port} | workers={args.workers} queue={args.max_queue} backlog={args.backlog} "
          f"| {args.classes} classes x {args.seats} seats | opens in {args.open_after}s", flush=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5099)
    parser.add_argument("--accounts", type=int, default=1000)
    parser.add_argument("--open-after", type=float, default=45)
    parser.add_argument("--workers", type=int, default=60, help="requests processed at the same time")
    parser.add_argument("--max-queue", type=int, default=600, help="waiting requests before answering 503")
    parser.add_argument("--backlog", type=int, default=128, help="TCP accept queue")
    parser.add_argument("--classes", type=int, default=30)
    parser.add_argument("--seats", type=int, default=30)
    parser.add_argument("--reset-rate", type=float, default=0.01)
    parser.add_argument("--bad-gateway-rate", type=float, default=0.01)
    parser.add_argument("--revoke-rate", type=float, default=0.002)
    parser.add_argument("--seed", type=int, default=7)
    cli = parser.parse_args()
    if resource is not None:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        target = 65536 if hard == resource.RLIM_INFINITY else min(hard, 65536)
        if soft < target:
            resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))
    asyncio.run(main(cli))
