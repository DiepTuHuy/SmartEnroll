#!/usr/bin/env python3
"""Câu hỏi: 1000 sinh viên khác đang chen vào cổng trường; tài khoản của tôi dùng SmartEnroll đăng nhập
giữa lúc đông nhất thì có vào được không, và giành được lớp khó nhất với xác suất bao nhiêu %?

Mỗi lần thử (trial):
  - cổng trường giả YẾU (mặc định 20 request xử lý cùng lúc, đăng nhập mất 0.5-1.5 giây/lần)
  - 1000 sinh viên 'người thật' (tests/crowd.py) ồ ạt đăng nhập trong 20 giây đầu, F5, rồi bấm đăng ký
  - ở giây thứ 8 (giữa lúc đông nhất), 4 tài khoản cùng bắt đầu và cùng nhắm 2 lớp bị tranh nhiều nhất:
        tool-normal : SmartEnroll bản mới, chế độ Thường   (code thật, tests/my_tool.py)
        tool-turbo  : SmartEnroll bản mới, chế độ Turbo    (code thật)
        human       : một sinh viên bình thường dùng trình duyệt
        oldtool     : SmartEnroll bản cũ (mô phỏng theo đúng các timeout của bản cũ)
  - mở đăng ký ở giây thứ 40, kết thúc ở giây thứ 100

Hai kiểu cổng trường quá tải:
  A_tu_choi_nhanh : hàng chờ đầy (300) là trả 503 ngay
  B_xep_hang_lau  : không từ chối, bắt xếp hàng; chờ quá 60 giây thì 504 (giống lỗi timeout thật)

Chạy:     venv/bin/python tests/login_chance.py --trials 20
Kết quả:  tests/output/login_chance_report.json + bảng tóm tắt in ra màn hình
"""
import argparse
import concurrent.futures
import json
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
PY = sys.executable

PROFILES = {
    "A_tu_choi_nhanh": {"workers": 20, "max_queue": 300, "gateway_timeout": 60},
    "B_xep_hang_lau": {"workers": 20, "max_queue": 100000, "gateway_timeout": 60},
}
PARTICIPANTS = ["tool-normal", "tool-turbo", "human", "oldtool"]


def stats_of(port, detail=True):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/__stats" + ("?detail=1" if detail else ""), timeout=20) as r:
        return json.loads(r.read())


def run_trial(profile_name, trial, port, a):
    prof = PROFILES[profile_name]
    work = Path(tempfile.mkdtemp(prefix=f"chance-{profile_name}-{trial}-"))
    t0 = time.time() + 4                       # give every process time to boot
    open_at = t0 + a.open_after
    end_at = open_at + a.run_after_open
    me_start = t0 + a.observer_start
    n = a.students
    users = {"human": f"SV{n + 1:04d}", "oldtool": f"SV{n + 2:04d}",
             "tool-normal": f"SV{n + 3:04d}", "tool-turbo": f"SV{n + 4:04d}"}
    seed = 1000 * (list(PROFILES).index(profile_name) + 1) + trial
    portal = subprocess.Popen(
        [PY, str(HERE / "fake_portal_server.py"), "--port", str(port), "--accounts", str(n), "--extra-accounts", "10",
         "--open-at", str(open_at), "--workers", str(prof["workers"]), "--max-queue", str(prof["max_queue"]),
         "--gateway-timeout", str(prof["gateway_timeout"]), "--login-service", a.login_service,
         "--register-service", a.register_service, "--page-service", a.page_service,
         "--classes", "30", "--seats", "30", "--seed", str(seed)],
        stdout=open(work / "portal.log", "w"), stderr=subprocess.STDOUT)
    procs = []
    try:
        for _ in range(100):
            try:
                stats_of(port, detail=False)
                break
            except Exception:
                time.sleep(0.1)
        crowd_out = work / "crowd.json"
        procs.append(subprocess.Popen(
            [PY, str(HERE / "crowd.py"), "--port", str(port), "--students", str(n), "--seed", str(seed),
             "--t0", str(t0), "--arrival-window", str(a.arrival_window), "--open-at", str(open_at), "--end-at", str(end_at),
             "--observer-start", str(me_start), "--observer-targets", a.targets, "--out", str(crowd_out)],
            stdout=open(work / "crowd.log", "w"), stderr=subprocess.STDOUT))
        tool_outs = {}
        for mode in ("normal", "turbo"):
            out = work / f"tool-{mode}.json"
            tool_outs[f"tool-{mode}"] = out
            procs.append(subprocess.Popen(
                [PY, str(HERE / "my_tool.py"), "--port", str(port), "--user", users[f"tool-{mode}"], "--start-at", str(me_start),
                 "--open-at", str(open_at), "--end-at", str(end_at), "--targets", a.targets, "--mode", mode, "--out", str(out)],
                stdout=open(work / f"tool-{mode}.log", "w"), stderr=subprocess.STDOUT))
        for p in procs:
            try:
                p.wait(timeout=end_at - time.time() + 60)
            except subprocess.TimeoutExpired:
                p.kill()
        final = stats_of(port)
    finally:
        for p in procs:
            if p.poll() is None:
                p.kill()
        portal.terminate()
        try:
            portal.wait(timeout=5)
        except Exception:
            portal.kill()

    crowd = json.loads(crowd_out.read_text()) if crowd_out.exists() else {}
    targets = [int(x) for x in a.targets.split(",")]
    per_user = final.get("per_user", {})
    started_rel = round(me_start - open_at, 3)
    result = {"profile": profile_name, "trial": trial, "crowd_logged_in_before_open": crowd.get("crowd_logged_in_before_open"),
              "demand": {str(c): crowd.get("demand", {}).get(str(c)) for c in targets}, "participants": {}}
    for kind in PARTICIPANTS:
        user = users[kind]
        if kind.startswith("tool"):
            info = json.loads(tool_outs[kind].read_text()) if tool_outs[kind].exists() else {}
        else:
            info = (crowd.get("observers") or {}).get(kind) or {}
        login_at = info.get("login_at")
        regs = {r["class"]: r for r in per_user.get(user, []) if r["at"] <= a.run_after_open}
        result["participants"][kind] = {
            "login_at": login_at,
            "login_wait_s": round(login_at - started_rel, 2) if login_at is not None else None,
            "login_attempts": info.get("login_attempts"),
            "classes": {str(c): ({"at": regs[c]["at"], "rank": regs[c]["rank"]} if c in regs else None) for c in targets},
            "note": info.get("stopped"),
        }
    (work / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))
    return result


def pct(k, n):
    return f"{k}/{n} ({round(100 * k / n) if n else 0}%)"


def summarize(results, a):
    lines = []
    report = {}
    targets = a.targets.split(",")
    for profile in PROFILES:
        rs = [r for r in results if r["profile"] == profile]
        if not rs:
            continue
        n = len(rs)
        crowd_in = [r["crowd_logged_in_before_open"] for r in rs if r["crowd_logged_in_before_open"] is not None]
        demand = {c: statistics.mean([r["demand"][c] for r in rs if r["demand"].get(c)]) for c in targets}
        lines.append(f"\n=== {profile}  ({n} lần thử, {a.students} sinh viên khác, "
                     f"trung bình {round(statistics.mean(crowd_in)) if crowd_in else '?'}/{a.students} người vào được trước giờ mở)")
        lines.append(f"    lớp nhắm tới: " + ", ".join(f"lớp {c}: ~{round(demand[c])} người giành 30 chỗ" for c in targets))
        header = f"    {'':12} {'vào trước giờ mở':>20} {'vào được (cả đợt)':>20} {'thời gian vào (trung vị)':>26}" + "".join(f" {'giành được lớp ' + c:>20}" for c in targets)
        lines.append(header)
        report[profile] = {}
        for kind in PARTICIPANTS:
            ps = [r["participants"][kind] for r in rs]
            before = sum(1 for p in ps if p["login_at"] is not None and p["login_at"] < 0)
            ever = sum(1 for p in ps if p["login_at"] is not None)
            waits = [p["login_wait_s"] for p in ps if p["login_wait_s"] is not None]
            got = {c: sum(1 for p in ps if p["classes"].get(c)) for c in targets}
            med = f"{statistics.median(waits):.1f}s" if waits else "-"
            lines.append(f"    {kind:12} {pct(before, n):>20} {pct(ever, n):>20} {med:>26}" + "".join(f" {pct(got[c], n):>20}" for c in targets))
            report[profile][kind] = {"login_before_open": before, "login_ever": ever, "trials": n,
                                     "login_wait_median_s": statistics.median(waits) if waits else None,
                                     "got_class": got}
    return "\n".join(lines), report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=20)
    ap.add_argument("--parallel", type=int, default=5)
    ap.add_argument("--students", type=int, default=1000)
    ap.add_argument("--profiles", default=",".join(PROFILES))
    ap.add_argument("--arrival-window", type=float, default=20)
    ap.add_argument("--observer-start", type=float, default=8, help="seconds after t0 when YOUR account starts logging in")
    ap.add_argument("--open-after", type=float, default=40)
    ap.add_argument("--run-after-open", type=float, default=60)
    ap.add_argument("--targets", default="1,16", help="the two most contested classes")
    ap.add_argument("--login-service", default="0.5,1.0")
    ap.add_argument("--register-service", default="0.1,0.2")
    ap.add_argument("--page-service", default="0.05,0.1")
    ap.add_argument("--base-port", type=int, default=5200)
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    jobs = [(p, t) for p in a.profiles.split(",") for t in range(a.trials)]
    print(f"{len(jobs)} trials, {a.parallel} at a time, ~{(a.open_after + a.run_after_open + 10) * len(jobs) / a.parallel / 60:.0f} min", flush=True)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.parallel) as ex:
        futures = {ex.submit(run_trial, p, t, a.base_port + i, a): (p, t) for i, (p, t) in enumerate(jobs)}
        for fut in concurrent.futures.as_completed(futures):
            p, t = futures[fut]
            try:
                r = fut.result()
                results.append(r)
                me = r["participants"]["tool-normal"]
                print(f"  done {p} #{t}: tool-normal login {me['login_wait_s']}s, classes {me['classes']}", flush=True)
            except Exception as e:
                print(f"  FAILED {p} #{t}: {e}", flush=True)
    table, report = summarize(results, a)
    (OUT / "login_chance_report.json").write_text(json.dumps({"params": vars(a), "summary": report, "trials": results},
                                                             ensure_ascii=False, indent=1))
    print(table)
    print(f"\nreport: {OUT / 'login_chance_report.json'}")


if __name__ == "__main__":
    main()
