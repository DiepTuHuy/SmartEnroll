#!/usr/bin/env python3
"""Load test backend SmartEnroll: N tài khoản giả cùng đăng nhập rồi cùng spam đăng ký,
trên cổng trường GIẢ có giới hạn năng lực (tests/fake_portal_server.py). Không chạm tới cổng thật.

Kịch bản giống Discord bot nhiều người dùng: N AppState trong MỘT tiến trình Python.
(Bản web thì mỗi sinh viên chạy bản riêng trên máy mình, nhẹ hơn rất nhiều so với bài này.)

Chạy:     venv/bin/python tests/load_test.py --accounts 1000
Kết quả:  tests/output/loadtest_report.json      số liệu + từng kiểm tra PASS/FAIL
          tests/output/loadtest_accounts.log     log của từng tài khoản giả
          tests/output/loadtest_timeline.csv     luồng / RAM / CPU / hàng đợi cổng giả theo từng giây
"""
import argparse
import csv
import json
import os
import random
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "output"

try:
    import resource
except ImportError:  # Windows
    resource = None


def say(*parts):
    print(*parts, file=sys.__stdout__, flush=True)


def raise_fd_limit():
    if resource is None:
        return
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    target = 65536 if hard == resource.RLIM_INFINITY else min(hard, 65536)
    if soft < target:
        resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))


def rss_mb():
    try:
        out = subprocess.run(["ps", "-o", "rss=", "-p", str(os.getpid())], capture_output=True, text=True, timeout=2).stdout
        return round(int(out.strip()) / 1024, 1)
    except Exception:
        return None


def portal_stats(port, detail=False):
    url = f"http://127.0.0.1:{port}/__stats" + ("?detail=1" if detail else "")
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read())


def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    k = min(len(values) - 1, max(0, round(p / 100 * (len(values) - 1))))
    return round(values[k], 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--accounts", type=int, default=1000)
    ap.add_argument("--wrong-passwords", type=int, default=10, help="accounts with a wrong password (must stop after 1 try)")
    ap.add_argument("--turbo-share", type=float, default=0.2)
    ap.add_argument("--open-after", type=float, default=45, help="seconds until the fake portal opens registration")
    ap.add_argument("--run-after-open", type=float, default=45)
    ap.add_argument("--login-timeout", type=float, default=40)
    ap.add_argument("--port", type=int, default=5099)
    ap.add_argument("--workers", type=int, default=60)
    ap.add_argument("--max-queue", type=int, default=600)
    ap.add_argument("--classes", type=int, default=30)
    ap.add_argument("--seats", type=int, default=30)
    ap.add_argument("--revoke-rate", type=float, default=0.002)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--tag", default="", help="suffix for output files")
    a = ap.parse_args()

    raise_fd_limit()
    OUT.mkdir(exist_ok=True)
    tag = f"_{a.tag}" if a.tag else ""
    tmp = tempfile.mkdtemp(prefix="smartenroll-load-")
    os.environ["HOME"] = tmp          # every account's config file goes here, never into the real home
    os.environ["USERPROFILE"] = tmp
    os.chdir(tmp)
    rng = random.Random(a.seed)

    portal_log = open(OUT / f"fake_portal{tag}.log", "w")
    server = subprocess.Popen(
        [sys.executable, str(HERE / "fake_portal_server.py"), "--port", str(a.port), "--accounts", str(a.accounts),
         "--open-after", str(a.open_after), "--workers", str(a.workers), "--max-queue", str(a.max_queue),
         "--classes", str(a.classes), "--seats", str(a.seats), "--revoke-rate", str(a.revoke_rate), "--seed", str(a.seed)],
        stdout=portal_log, stderr=subprocess.STDOUT)
    try:
        for _ in range(100):
            try:
                first = portal_stats(a.port)
                break
            except Exception:
                time.sleep(0.1)
        else:
            raise SystemExit("fake portal did not start")
        open_at = time.time() + first["open_in"]

        # ---------------------------------------------------------------- client under test
        sys.path.insert(0, str(ROOT))
        print_sink = open(OUT / f"loadtest_print{tag}.log", "w")
        sys.stdout = print_sink  # core_state prints every log line; keep the console readable
        import requests
        from requests.adapters import HTTPAdapter
        import core_state

        base = f"http://127.0.0.1:{a.port}"

        class ToFakePortal(HTTPAdapter):
            """Same pool settings as production, but every portal URL is sent to the local fake."""
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

        thread_errors = []
        threading.excepthook = lambda args: thread_errors.append(f"{args.thread.name}: {args.exc_type.__name__}: {args.exc_value}")

        timeline = []
        stop_monitor = threading.Event()

        def monitor():
            while not stop_monitor.is_set():
                try:
                    ps = portal_stats(a.port)
                except Exception:
                    ps = {}
                times = os.times()
                timeline.append({
                    "t": round(time.time() - open_at, 1),
                    "threads": threading.active_count(),
                    "rss_mb": rss_mb(),
                    "cpu_s": round(times.user + times.system, 1),
                    "portal_waiting": ps.get("waiting"),
                    "portal_processing": ps.get("processing"),
                    "portal_requests": ps.get("requests_total"),
                    "seats_left": ps.get("seats_left"),
                })
                stop_monitor.wait(1.0)

        threading.Thread(target=monitor, name="monitor", daemon=True).start()

        say(f"== {a.accounts} accounts | registration opens in {first['open_in']:.0f}s | "
            f"portal: {a.workers} workers, queue {a.max_queue}, {a.classes}x{a.seats} seats")
        t = time.time()
        states = [core_state.get_app_state(f"lt{i:04d}") for i in range(a.accounts)]
        say(f"   created {len(states)} accounts in {time.time() - t:.2f}s, threads={threading.active_count()}")

        # ---------------------------------------------------------------- 1. everyone logs in at once
        wrong = set(range(a.accounts - a.wrong_passwords, a.accounts))
        t_login = time.time()
        for i, st in enumerate(states):
            user = f"SV{i + 1:04d}"
            st.start_login_job(user, "sai-mat-khau" if i in wrong else f"pw-{user}", persistent=True)
        while time.time() - t_login < a.login_timeout and any(st.login_job.get("status") == "running" for st in states):
            time.sleep(0.25)
        login_wall = time.time() - t_login
        logged = [i for i, st in enumerate(states) if st.login_job.get("status") == "success"]
        login_times = [states[i].login_job["finished_at"] - states[i].login_job["started_at"] for i in logged]
        say(f"1) login storm: {len(logged)}/{a.accounts - a.wrong_passwords} valid accounts in, wall {login_wall:.1f}s, "
            f"p50 {percentile(login_times, 50)}s p95 {percentile(login_times, 95)}s max {percentile(login_times, 100)}s, "
            f"threads={threading.active_count()}")

        # ---------------------------------------------------------------- 2. everyone starts spamming before opening
        half = a.classes // 2
        weights_a = [1 / (k ** 0.8) for k in range(1, half + 1)]          # a few classes are far more popular
        weights_b = [1 / (k ** 0.8) for k in range(1, a.classes - half + 1)]
        plans = {}
        spam_threads = []
        start_errors = []
        for i in logged:
            ca = rng.choices(range(1, half + 1), weights_a)[0]
            cb = rng.choices(range(half + 1, a.classes + 1), weights_b)[0]
            mode = "turbo" if rng.random() < a.turbo_share else "normal"
            targets = [{"id": ca, "name": f"Môn A - lớp {ca}"}, {"id": cb, "name": f"Môn B - lớp {cb}"}]
            plans[i] = (mode, [ca, cb])
            th = threading.Thread(target=states[i].run_spam_loop, args=(targets, mode), name=f"spam-{i}", daemon=True)
            try:
                th.start()
                spam_threads.append((i, th))
            except RuntimeError as e:  # e.g. "can't start new thread"
                start_errors.append(f"account {i}: {e}")
        say(f"2) {len(spam_threads)} accounts spamming ({sum(1 for m, _ in plans.values() if m == 'turbo')} turbo) "
            f"{max(0, open_at - time.time()):.0f}s before opening, threads={threading.active_count()}")

        end_at = open_at + a.run_after_open
        while time.time() < end_at:
            time.sleep(0.5)

        # ---------------------------------------------------------------- 3. stop button for everyone
        busy_cpu_window = [row for row in timeline if 0 <= row["t"] <= a.run_after_open]
        t_stop = time.time()
        for st in states:
            st.is_spamming = False
        for _, th in spam_threads:
            th.join(timeout=max(0.05, t_stop + 15 - time.time()))
        callers_alive = sum(th.is_alive() for _, th in spam_threads)
        stop_latency = time.time() - t_stop
        # Requests already sent keep going until the portal answers (a success after "stop" still counts),
        # so wait for every lane to wind down before taking the final snapshot.
        def lanes_left(st):
            run = getattr(st, "_spam_run", None)
            return max(0, getattr(run, "lanes_left", 0)) if run else 0
        settle_deadline = time.time() + 75
        while time.time() < settle_deadline and sum(lanes_left(st) for st in states) > 0:
            time.sleep(0.25)
        lanes_still_running = sum(lanes_left(st) for st in states)
        settle_s = time.time() - t_stop
        time.sleep(1.0)
        threads_after = threading.active_count()
        say(f"3) stop: all spam loops returned in {stop_latency:.2f}s (still running: {callers_alive}); "
            f"in-flight requests finished after {settle_s:.1f}s; threads after={threads_after}")

        stop_monitor.set()
        final = portal_stats(a.port, detail=True)
        sys.stdout = sys.__stdout__
        print_sink.close()

        # ---------------------------------------------------------------- results + checks
        per_user = final.get("per_user", {})
        first_success = sorted(min(r["at"] for r in regs) for regs in per_user.values() if regs)
        mismatches = []
        for i in logged:
            user = f"SV{i + 1:04d}"
            portal_regs = len(per_user.get(user, []))
            client_ok = states[i].stats.get("success_count", 0)
            if portal_regs != client_ok:
                mismatches.append(f"{user}: portal {portal_regs} vs client {client_ok}")
        wrong_attempts = {f"SV{i + 1:04d}": final["login_attempts"].get(f"SV{i + 1:04d}", 0) for i in wrong}
        relogins = final["counts"].get("login:ok", 0) - len(logged)   # real logins after the first one
        # every class must end up either full, or holding everyone who wanted it
        demand = {}
        for mode, wanted in plans.values():
            for cid in wanted:
                demand[cid] = demand.get(cid, 0) + 1
        taken = {}
        for regs in per_user.values():
            for r in regs:
                taken[r["class"]] = taken.get(r["class"], 0) + 1
        short = {cid: (taken.get(cid, 0), min(d, a.seats)) for cid, d in demand.items() if taken.get(cid, 0) != min(d, a.seats)}
        max_possible = sum(min(d, a.seats) for d in demand.values())
        peak_threads = max((row["threads"] for row in timeline), default=threading.active_count())
        peak_rss = max((row["rss_mb"] or 0 for row in timeline), default=0)
        cpu_used = (busy_cpu_window[-1]["cpu_s"] - busy_cpu_window[0]["cpu_s"]) if len(busy_cpu_window) > 1 else None
        cpu_share = round(cpu_used / (busy_cpu_window[-1]["t"] - busy_cpu_window[0]["t"]), 2) if cpu_used else None
        req_window = [row for row in timeline if 0 <= row["t"] <= a.run_after_open and row["portal_requests"]]
        req_rate = (round((req_window[-1]["portal_requests"] - req_window[0]["portal_requests"]) /
                          (req_window[-1]["t"] - req_window[0]["t"]), 1) if len(req_window) > 1 else None)
        counts = final["counts"]

        checks = [
            ("every valid account logged in despite the login storm", len(logged) == a.accounts - a.wrong_passwords,
             f"{len(logged)}/{a.accounts - a.wrong_passwords}"),
            ("wrong-password accounts stopped after exactly 1 attempt", all(v == 1 for v in wrong_attempts.values()),
             f"attempts={sorted(set(wrong_attempts.values()))}"),
            ("every class ended full, or with everyone who wanted it", not short,
             f"{final['registrations']}/{max_possible} reachable seats taken" + (f", short: {dict(list(short.items())[:5])}" if short else "")),
            ("client success count == portal records for every account", not mismatches,
             f"{len(mismatches)} mismatches" + (f", e.g. {mismatches[:3]}" if mismatches else "")),
            ("no account registered more than its 2 classes", all(len(v) <= 2 for v in per_user.values()),
             f"max {max((len(v) for v in per_user.values()), default=0)} per account"),
            ("revoked tokens recovered by automatic re-login", final["revoked"] == 0 or relogins > 0,
             f"portal revoked {final['revoked']}, client re-logins {relogins}"),
            ("stop button ends every spam loop within 3s", callers_alive == 0 and stop_latency <= 3,
             f"{stop_latency:.2f}s"),
            ("every lane wound down after stop (in-flight requests included)", lanes_still_running == 0,
             f"{lanes_still_running} lanes left, {settle_s:.1f}s"),
            ("no crashed threads, no thread start failures", not thread_errors and not start_errors,
             f"{len(thread_errors)} crashes, {len(start_errors)} start failures"),
        ]
        report = {
            "params": vars(a),
            "login": {"logged_in": len(logged), "wall_s": round(login_wall, 2), "p50_s": percentile(login_times, 50),
                      "p95_s": percentile(login_times, 95), "max_s": percentile(login_times, 100)},
            "registration": {"seats_total": final["seats_total"], "reachable_seats": max_possible,
                             "registrations": final["registrations"],
                             "full_after_open_s": final["full_after_open"], "accounts_with_a_seat": len(first_success),
                             "first_seat_p50_s": percentile(first_success, 50), "first_seat_p95_s": percentile(first_success, 95)},
            "client_process": {"peak_threads": peak_threads, "threads_after_stop": threads_after, "peak_rss_mb": peak_rss,
                               "cpu_cores_used_while_spamming": cpu_share, "relogins": relogins,
                               "thread_errors": thread_errors[:20], "start_errors": start_errors[:20]},
            "portal": {"requests_per_s_while_open": req_rate, "max_waiting": final["max_waiting"],
                       "max_processing": final["max_processing"], "revoked_tokens": final["revoked"], "counts": counts},
            "checks": [{"name": n, "pass": bool(ok), "detail": d} for n, ok, d in checks],
        }
        (OUT / f"loadtest_report{tag}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
        with open(OUT / f"loadtest_timeline{tag}.csv", "w", newline="") as f:
            if timeline:
                writer = csv.DictWriter(f, fieldnames=list(timeline[0].keys()))
                writer.writeheader()
                writer.writerows(timeline)
        with open(OUT / f"loadtest_accounts{tag}.log", "w", encoding="utf-8") as f:
            for i, st in enumerate(states):
                user = f"SV{i + 1:04d}"
                mode, wanted = plans.get(i, ("-", []))
                job = st.login_job
                f.write(f"===== {user} | login={job.get('status')} attempts={job.get('attempts')} | mode={mode} "
                        f"wanted={wanted} got={[r['class'] for r in per_user.get(user, [])]} | stats={st.stats}\n")
                for line in st.logs:
                    f.write(f"  {line}\n")

        last_seat = max((r["at"] for regs in per_user.values() for r in regs), default=None)
        say(f"4) seats: {final['registrations']} taken of {max_possible} reachable ({final['seats_total']} total); "
            f"first seat per student p50 {percentile(first_success, 50)}s p95 {percentile(first_success, 95)}s, "
            f"last seat at {last_seat}s after opening")
        say(f"   client: peak threads {peak_threads}, peak RAM {peak_rss} MB, CPU {cpu_share} cores while spamming, "
            f"re-logins {relogins} (portal revoked {final['revoked']})")
        say(f"   portal: {req_rate} req/s while open, max queue {final['max_waiting']}, "
            f"503 answers {sum(v for k, v in counts.items() if k.endswith(':503'))}, "
            f"resets {sum(v for k, v in counts.items() if k.endswith(':reset'))}")
        say("")
        for name, ok, detail in checks:
            say(f"{'PASS' if ok else 'FAIL'}  {name}  ({detail})")
        say(f"\nreport: {OUT / f'loadtest_report{tag}.json'}\naccount logs: {OUT / f'loadtest_accounts{tag}.log'}")
        return 0 if all(ok for _, ok, _ in checks) else 1
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except Exception:
            server.kill()
        portal_log.close()


if __name__ == "__main__":
    sys.exit(main())
