#!/usr/bin/env python3
"""Đám đông sinh viên 'người thật' (dùng trình duyệt, không dùng tool) chen vào cổng trường giả.

Mô hình hành vi (là GIẢ ĐỊNH, chỉnh được bên dưới):
  - vào đăng nhập rải rác trong `--arrival-window` giây đầu
  - bấm đăng nhập; trang quay quá 15-40 giây thì bấm lại; lỗi/503 thì 2-6 giây sau bấm lại; không bỏ cuộc
  - vào được thì mở trang đăng ký (tải danh sách môn), trong lúc chờ giờ mở thì F5 mỗi 8-20 giây
  - tới giờ: bấm "Đăng ký" lớp mình muốn, 1-3 giây bấm một lần, mỗi lần chờ tối đa 15-30 giây
  - lớp đầy: một nửa đổi sang lớp khác cùng môn, một nửa cứ bấm tiếp; bị đá ra (401) thì đăng nhập lại

Ngoài đám đông còn 2 'người quan sát' vào cùng lúc với tài khoản dùng tool mới và nhắm cùng 2 lớp:
  - human : một sinh viên bình thường y như đám đông nhưng không đổi lớp
  - oldtool: mô phỏng SmartEnroll BẢN CŨ: mỗi lần đăng nhập chờ tối đa 10 giây (kết nối 10s, đọc 10s),
             hỏng thì 1 giây sau thử lại (chế độ "Spam đăng nhập"); đăng ký chờ tối đa 5 giây/request,
             nghỉ 0.5 giây giữa các lớp, 1 giây giữa các vòng; gặp 401 mà đăng nhập lại hỏng thì dừng hẳn.
"""
import argparse
import asyncio
import json
import random
import time

import aiohttp

try:
    import resource
except ImportError:
    resource = None

UA = "Mozilla/5.0"


class Crowd:
    def __init__(self, a):
        self.a = a
        self.base = f"http://127.0.0.1:{a.port}"
        self.rng = random.Random(a.seed)
        self.results = {}

    # ------------------------------------------------------------------ helpers
    def rel(self):
        return round(time.time() - self.a.open_at, 3)

    async def sleep_until(self, t):
        delay = t - time.time()
        if delay > 0:
            await asyncio.sleep(delay)

    async def call(self, method, path, timeout, token=None, json_body=None):
        """Một request. Trả về (status, json|None); (None, None) nếu timeout / mất kết nối."""
        headers = {"User-Agent": UA}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            async with self.session.request(method, self.base + path, json=json_body, headers=headers, timeout=timeout) as r:
                try:
                    data = await r.json(content_type=None)
                except Exception:
                    data = None
                return r.status, data
        except (asyncio.TimeoutError, aiohttp.ClientError, ConnectionError):
            return None, None

    async def login(self, user, timeout):
        status, data = await self.call("POST", "/api/v1/user/login?g-recaptcha-response=x", timeout,
                                       json_body={"username": user, "password": f"pw-{user}"})
        if status == 200 and isinstance(data, dict) and data.get("success"):
            return data["token"]
        return None

    # ------------------------------------------------------------------ a normal student in a browser
    async def human(self, user, arrive_at, wanted, may_switch, rng):
        res = self.results[user] = {"kind": "human", "login_at": None, "login_attempts": 0}
        await self.sleep_until(arrive_at)
        token = None
        current = list(wanted)  # one class per subject
        done = [False] * len(current)
        while time.time() < self.a.end_at and not all(done):
            while token is None and time.time() < self.a.end_at:
                res["login_attempts"] += 1
                token = await self.login(user, aiohttp.ClientTimeout(total=rng.uniform(15, 40)))
                if token is None:
                    await asyncio.sleep(rng.uniform(2, 6))
                elif res["login_at"] is None:
                    res["login_at"] = self.rel()
            if token is None:
                break
            await self.call("GET", "/api/v1/dkhp/getHocPhanHocMoi?idDot=77", aiohttp.ClientTimeout(total=30), token)
            while time.time() < self.a.open_at - 0.5:            # F5 while waiting for opening
                await asyncio.sleep(min(rng.uniform(8, 20), max(0.1, self.a.open_at - time.time())))
                if time.time() < self.a.open_at - 0.5:
                    await self.call("GET", "/api/v1/dkhp/getHocPhanHocMoi?idDot=77", aiohttp.ClientTimeout(total=30), token)
            for idx in range(len(current)):
                while not done[idx] and token is not None and time.time() < self.a.end_at:
                    status, data = await self.call("POST", f"/api/v1/dkhp/dangKyLopHocPhan?idLopHocPhan={current[idx]}",
                                                   aiohttp.ClientTimeout(total=rng.uniform(15, 30)), token)
                    msg = (data or {}).get("message", "") if isinstance(data, dict) else ""
                    if status == 401:
                        token = None
                        break
                    if status == 200 and isinstance(data, dict) and (data.get("success") or "đã đăng ký" in msg):
                        done[idx] = True
                        break
                    if "đủ số lượng" in msg and may_switch and rng.random() < 0.5:
                        lo, hi = self.subject_range(current[idx])
                        current[idx] = rng.choice([c for c in range(lo, hi + 1) if c != current[idx]])
                    if "Chưa đến" in msg:
                        await asyncio.sleep(rng.uniform(1, 2))
                    else:
                        await asyncio.sleep(rng.uniform(1, 3))
                if token is None:
                    break

    def subject_range(self, class_id):
        half = self.a.classes // 2
        return (1, half) if class_id <= half else (half + 1, self.a.classes)

    # ------------------------------------------------------------------ the OLD SmartEnroll (before this branch)
    async def old_tool(self, user, arrive_at, wanted):
        res = self.results[user] = {"kind": "oldtool", "login_at": None, "login_attempts": 0, "stopped": None}
        login_timeout = aiohttp.ClientTimeout(sock_connect=10, sock_read=10)
        await self.sleep_until(arrive_at)
        token = None
        while token is None and time.time() < self.a.end_at:     # "Spam đăng nhập" mode in the old UI
            res["login_attempts"] += 1
            token = await self.login(user, login_timeout)
            if token is None:
                await asyncio.sleep(1.0)
        if token is None:
            return
        res["login_at"] = self.rel()
        await self.call("GET", "/api/v1/dkhp/getDot", aiohttp.ClientTimeout(sock_connect=5, sock_read=5), token)
        reg_timeout = aiohttp.ClientTimeout(sock_connect=5, sock_read=5)
        left = list(wanted)
        while left and time.time() < self.a.end_at:
            next_round = []
            for class_id in left:
                status, data = await self.call("POST", f"/api/v1/dkhp/dangKyLopHocPhan?idLopHocPhan={class_id}", reg_timeout, token)
                if status == 401:                                   # one re-login, else give up for good
                    res["login_attempts"] += 1
                    token = await self.login(user, login_timeout)
                    if token:
                        status, data = await self.call("POST", f"/api/v1/dkhp/dangKyLopHocPhan?idLopHocPhan={class_id}", reg_timeout, token)
                    if not token or status == 401:
                        res["stopped"] = "token hết hạn, bản cũ dừng spam"
                        return
                msg = (data or {}).get("message", "") if isinstance(data, dict) else ""
                ok = status == 200 and isinstance(data, dict) and (data.get("success") or "đã đăng ký" in msg or "Trùng lịch" in msg)
                if not ok:
                    next_round.append(class_id)
                await asyncio.sleep(0.5)
            left = next_round
            if left:
                await asyncio.sleep(1.0)

    # ------------------------------------------------------------------ run everything
    async def run(self):
        a = self.a
        connector = aiohttp.TCPConnector(limit=0, force_close=False)
        async with aiohttp.ClientSession(connector=connector) as self.session:
            tasks = []
            half = a.classes // 2
            weights_a = [1 / (k ** 0.8) for k in range(1, half + 1)]
            weights_b = [1 / (k ** 0.8) for k in range(1, a.classes - half + 1)]
            demand = {}
            for i in range(1, a.students + 1):
                rng = random.Random(self.rng.random())
                wanted = [rng.choices(range(1, half + 1), weights_a)[0], rng.choices(range(half + 1, a.classes + 1), weights_b)[0]]
                for c in wanted:
                    demand[c] = demand.get(c, 0) + 1
                arrive = a.t0 + rng.uniform(0, a.arrival_window)
                tasks.append(asyncio.ensure_future(self.human(f"SV{i:04d}", arrive, wanted, True, rng)))
            targets = [int(x) for x in a.observer_targets.split(",")]
            tasks.append(asyncio.ensure_future(self.human(f"SV{a.students + 1:04d}", a.observer_start, targets, False, random.Random(self.rng.random()))))
            tasks.append(asyncio.ensure_future(self.old_tool(f"SV{a.students + 2:04d}", a.observer_start, targets)))
            # hard stop at the end of the window (requests still in flight are simply abandoned)
            _, pending = await asyncio.wait(tasks, timeout=max(1.0, a.end_at - time.time() + 1))
            for t in pending:
                t.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        summary = {
            "crowd_logged_in_before_open": sum(1 for u, r in self.results.items() if r["kind"] == "human"
                                                and r["login_at"] is not None and r["login_at"] < 0
                                                and u not in (f"SV{a.students + 1:04d}",)),
            "crowd_size": a.students,
            "demand": demand,
            "observers": {
                "human": self.results.get(f"SV{a.students + 1:04d}"),
                "oldtool": self.results.get(f"SV{a.students + 2:04d}"),
            },
        }
        with open(a.out, "w") as f:
            json.dump(summary, f)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--students", type=int, default=1000)
    ap.add_argument("--classes", type=int, default=30)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--t0", type=float, required=True)
    ap.add_argument("--arrival-window", type=float, default=20)
    ap.add_argument("--open-at", type=float, required=True)
    ap.add_argument("--end-at", type=float, required=True)
    ap.add_argument("--observer-start", type=float, required=True)
    ap.add_argument("--observer-targets", default="1,16")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if resource is not None:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        target = 65536 if hard == resource.RLIM_INFINITY else min(hard, 65536)
        if soft < target:
            resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))
    asyncio.run(Crowd(args).run())
