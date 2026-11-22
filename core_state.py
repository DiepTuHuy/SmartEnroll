import os
import json
import base64
import heapq
import itertools
import weakref
import concurrent.futures
import threading
import time
import random
import string
import unicodedata
from collections import namedtuple

import requests
import urllib3
from requests.adapters import HTTPAdapter
from auto_config import get_auto_config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# MAPPING CÁC CA HỌC
CA_HOC = {
    "Ca 1 (Tiết 1-3)":   [1, 2, 3],
    "Ca 2 (Tiết 4-6)":   [4, 5, 6],
    "Ca 3 (Tiết 7-9)":   [7, 8, 9],
    "Ca 4 (Tiết 10-12)": [10, 11, 12],
    "Ca 5 (Tiết 13-15)": [13, 14, 15]
}

PORTAL = "https://portal.ut.edu.vn"
LOGIN_URL = f"{PORTAL}/api/v1/user/login"
DOT_URL = f"{PORTAL}/api/v1/dkhp/getDot"
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# --- CHIẾN LƯỢC CHỊU TẢI ---
# Cổng trường là 1 máy nginx. Giờ cao điểm nó (a) bỏ rơi kết nối mới -> ConnectTimeout,
# hoặc (b) nhận request rồi xử lý rất chậm / trả 502-504.
# - CONNECT_TIMEOUT ngắn: không bắt tay được thì mở kết nối mới sớm, đừng chờ vô ích.
# - READ_TIMEOUT dài: request đã lọt vào hàng đợi của server, bỏ ngang là mất lượt.
CONNECT_TIMEOUT = 6
READ_TIMEOUT = 45
LOGIN_READ_TIMEOUT = 60
REGISTER_READ_TIMEOUT = 60

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524}

# Giới hạn số request đăng ký đang bay cùng lúc (tránh bị chặn IP vì "flood").
MAX_INFLIGHT_REGISTER = 12
TURBO_LANES_PER_CLASS = 3
# Số request đăng ký được chờ cùng lúc cho CẢ tiến trình (mọi tài khoản cộng lại). Một máy một sinh viên
# không bao giờ chạm tới; chỉ có tác dụng khi Discord bot phục vụ rất nhiều người trong cùng một tiến trình.
SPAM_MAX_WORKERS = int(os.environ.get("SMARTENROLL_SPAM_WORKERS", "256"))
KEEPALIVE_TICK = 30

# Token cổng trường là JWT sống 30 ngày -> chỉ gia hạn khi còn dưới 1 giờ.
TOKEN_REFRESH_MARGIN = 3600
# Token không đọc được hạn: giữ nhịp gia hạn 10 phút như bản cũ.
UNKNOWN_EXPIRY_REFRESH_INTERVAL = 600
# Hỏi cổng trường "token còn sống không?" mỗi 4 phút khi đang treo máy chờ giờ đăng ký.
# Hạn 30 ngày chỉ là con số ghi trong token; server trường vẫn có thể hủy sớm hơn.
# Nhịp này vừa giữ phiên không bị coi là "bỏ quên", vừa phát hiện token chết từ lúc cổng còn vắng.
HEARTBEAT_INTERVAL = 240

# Cùng một thông báo từ chối lặp lại quá nhiều lần -> dừng, tránh khóa tài khoản.
MAX_IDENTICAL_LOGIN_REJECTIONS = 8

_CREDENTIAL_HINTS = (
    "mật khẩu", "mat khau", "password", "tài khoản", "tai khoan",
    "không tồn tại", "không chính xác", "không đúng", "bị khóa", "bị khoá", "locked",
)
_BUSY_HINTS = ("bận", "quá tải", "thử lại", "try again", "timeout", "busy")

_LoginAttempt = namedtuple("_LoginAttempt", "kind message data retry_after timed_out rejected")


def _nfc(text):
    return unicodedata.normalize("NFC", text or "")


def _looks_like_bad_credentials(message):
    m = _nfc(message).lower()
    if any(h in m for h in _BUSY_HINTS):
        return False
    return any(h in m for h in _CREDENTIAL_HINTS)


def _jwt_claims(token):
    """Đọc phần payload của JWT (không xác thực chữ ký), {} nếu không đọc được."""
    try:
        parts = (token or "").replace("Bearer ", "").strip().split(".")
        if len(parts) != 3:
            return {}
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return claims if isinstance(claims, dict) else {}
    except Exception:
        return {}


def _jwt_exp(token):
    """Thời điểm hết hạn (epoch giây) của JWT, None nếu không đọc được."""
    exp = _jwt_claims(token).get("exp")
    try:
        return float(exp) if exp is not None else None
    except (TypeError, ValueError):
        return None


def _normalize_timeout(timeout, read_default=READ_TIMEOUT):
    if isinstance(timeout, tuple):
        return timeout
    read = read_default if timeout is None else max(float(timeout), read_default)
    return (CONNECT_TIMEOUT, read)


def _retry_after_seconds(resp):
    value = resp.headers.get("Retry-After") if resp is not None else None
    if not value:
        return None
    try:
        return min(max(float(value), 0.0), 30.0)
    except ValueError:
        return None


def _backoff(attempt, base=0.5, cap=5.0):
    """Exponential backoff có jitter: các lần thử không dồn vào cùng một nhịp."""
    return random.uniform(base * 0.5, min(cap, base * (2 ** min(attempt, 8))))


def _describe_exception(exc):
    """Trả về (loại, thông báo dễ hiểu). loại = 'timeout' | 'error'."""
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return "timeout", "Cổng trường không nhận kết nối (đang quá tải)"
    if isinstance(exc, requests.exceptions.ReadTimeout):
        return "timeout", "Cổng trường đã nhận yêu cầu nhưng xử lý quá lâu"
    if isinstance(exc, requests.exceptions.SSLError):
        return "error", "Lỗi SSL khi kết nối cổng trường"
    if isinstance(exc, requests.exceptions.ConnectionError):
        return "error", "Kết nối tới cổng trường bị ngắt"
    return "error", f"Lỗi mạng: {exc}"


def _sleep_unless_stopped(delay, should_continue=None, wake_event=None):
    """Ngủ `delay` giây; dừng sớm khi should_continue() trả về False.

    Có wake_event thì chờ thẳng trên Event (không thức dậy định kỳ). Bản cũ thức 10 lần/giây
    để kiểm tra; nhân với vài nghìn luồng khi chạy nhiều tài khoản là đủ làm tiến trình nghẽn GIL.
    """
    end = time.monotonic() + max(0.0, delay)
    while True:
        if should_continue is not None and not should_continue():
            return False
        remaining = end - time.monotonic()
        if remaining <= 0:
            return True
        if wake_event is not None:
            if wake_event.wait(remaining):
                return bool(should_continue()) if should_continue is not None else False
        else:
            time.sleep(min(0.25, remaining))


def _new_http_session():
    session = requests.Session()
    # Tự xử lý retry ở tầng trên để kiểm soát backoff, nên tắt retry ngầm của urllib3.
    adapter = HTTPAdapter(pool_connections=20, pool_maxsize=64, max_retries=0)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# ---------------------------------------------------------------- shared engine
# Dùng chung cho mọi tài khoản trong tiến trình, để số luồng KHÔNG tăng theo số tài khoản.

# Việc nền nhỏ: kiểm tra token lúc khởi động, cập nhật đợt học, heartbeat.
_background = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="smartenroll-bg")


class _SpamScheduler:
    """Một luồng hẹn giờ + một nhóm luồng làm việc, dùng chung cho mọi chiến dịch spam.

    Mỗi 'làn' đăng ký là một việc nhỏ: gửi đúng 1 request rồi tự hẹn lần chạy kế tiếp.
    Trong lúc chờ tới lượt, làn không giữ luồng nào và không tốn CPU.
    """

    def __init__(self, workers):
        self._heap = []
        self._cv = threading.Condition()
        self._seq = itertools.count()
        self._pool = concurrent.futures.ThreadPoolExecutor(max_workers=workers, thread_name_prefix="smartenroll-spam")
        threading.Thread(target=self._dispatch, name="smartenroll-spam-scheduler", daemon=True).start()

    def call_later(self, delay, fn):
        when = time.monotonic() + max(0.0, delay)
        with self._cv:
            heapq.heappush(self._heap, (when, next(self._seq), fn))
            self._cv.notify()

    def _dispatch(self):
        while True:
            with self._cv:
                while True:
                    if not self._heap:
                        self._cv.wait()
                        continue
                    delay = self._heap[0][0] - time.monotonic()
                    if delay <= 0:
                        fn = heapq.heappop(self._heap)[2]
                        break
                    self._cv.wait(delay)
            self._pool.submit(fn)


_scheduler_instance = None
_scheduler_guard = threading.Lock()


def _spam_scheduler():
    global _scheduler_instance
    if _scheduler_instance is None:
        with _scheduler_guard:
            if _scheduler_instance is None:
                _scheduler_instance = _SpamScheduler(SPAM_MAX_WORKERS)
    return _scheduler_instance


# Một luồng giữ phiên cho mọi tài khoản (bản cũ: mỗi tài khoản một luồng ngủ/thức riêng).
_live_states = weakref.WeakSet()
_keepalive_started = False
_keepalive_guard = threading.Lock()


def _start_keepalive():
    global _keepalive_started
    with _keepalive_guard:
        if _keepalive_started:
            return
        _keepalive_started = True
    threading.Thread(target=_keepalive_loop, name="smartenroll-keepalive", daemon=True).start()


def _keepalive_loop():
    while True:
        time.sleep(KEEPALIVE_TICK)
        for state in list(_live_states):
            if not state._keepalive_busy:
                state._keepalive_busy = True
                _background.submit(state._safe_keepalive_tick)


class _SpamRun:
    """Một chiến dịch spam (một lần bấm "Chạy")."""

    def __init__(self, state, run_id, turbo):
        self.state = state
        self.run_id = run_id
        self.turbo = turbo
        self.stats = {"total_requests": 0, "success_count": 0, "error_count": 0, "timeouts": 0, "relogins": 0}
        self.stop_event = threading.Event()   # đã bấm dừng / bị hủy
        self.finished = threading.Event()     # đã dừng, hoặc mọi làn đã xong
        self.inflight = threading.Semaphore(MAX_INFLIGHT_REGISTER)
        self.lanes_left = 0
        self.aborted = False
        self._lock = threading.Lock()

    def active(self):
        return not self.stop_event.is_set()

    def stop(self):
        self.stop_event.set()
        self.finished.set()

    def lane_finished(self):
        with self._lock:
            self.lanes_left -= 1
            if self.lanes_left <= 0:
                self.finished.set()


class _SpamLane:
    """Một 'làn' gửi request cho 1 lớp: mỗi lần chạy gửi đúng 1 request rồi tự hẹn lần kế tiếp."""

    def __init__(self, run, target, done):
        self.run = run
        self.target = target
        self.done = done              # dùng chung giữa các làn của cùng một lớp
        self.fail_streak = 0
        self.seen_gen = None
        self.waiting_relogin = False
        self.ended = False

    def active(self):
        return self.run.active() and not self.done.is_set()

    def schedule(self, delay):
        _spam_scheduler().call_later(delay, self.step)

    def finish(self):
        if not self.ended:
            self.ended = True
            self.run.lane_finished()

    def step(self):
        try:
            self._step()
        except Exception as e:  # một lỗi lạ không được giết chết làn
            self.run.state.log(f"⚠️ Lỗi không mong đợi ở làn đăng ký: {e}")
            if self.active():
                self.schedule(1.0)
            else:
                self.finish()

    def _step(self):
        run, state, t = self.run, self.run.state, self.target
        name = t.get('name') or t.get('id')
        target_id = t.get('id')
        if not self.active():
            return self.finish()

        if self.waiting_relogin:
            if state._token_gen != self.seen_gen:
                self.waiting_relogin = False
                state._bump(run.stats, "relogins")
            elif run.aborted:
                return self.finish()
            else:
                return self.schedule(0.3)

        # Giới hạn số request đang bay của tài khoản này; không chặn luồng làm việc, chỉ hẹn lại.
        if not run.inflight.acquire(blocking=False):
            return self.schedule(0.05)
        self.seen_gen = state._token_gen
        try:
            outcome, msg, retry_after = state._register_once(t)
        except Exception as e:
            outcome, msg, retry_after = "overloaded", f"Lỗi không mong đợi: {e}", None
        finally:
            run.inflight.release()
        state._bump(run.stats, "total_requests")

        if outcome in ("success", "already"):
            # Kết quả thành công vẫn được ghi nhận kể cả khi người dùng vừa bấm dừng.
            with state._stats_lock:
                first = not self.done.is_set()
                self.done.set()
            if first:
                state._bump(run.stats, "success_count")
                if outcome == "success":
                    state.log(f"🎉 ĐĂNG KÝ THÀNH CÔNG: {name} (ID: {target_id})")
                else:
                    state.log(f"ℹ️ {name}: {msg}")
            return self.finish()

        if not self.active():
            return self.finish()

        if outcome == "expired":
            state._log_deduped(run.run_id, target_id, f"🔑 {name}: token hết hạn, đang tự đăng nhập lại...")
            status = state._begin_spam_relogin(self.seen_gen, run)
            if status == "ready":
                state._bump(run.stats, "relogins")
                return self.schedule(0)
            if status == "no_credentials":
                state._abort_run(run, f"💀 Không tự đăng nhập lại được ({state.last_login_error}). "
                                      "Dừng spam, vui lòng đăng nhập lại.")
                return self.finish()
            self.waiting_relogin = True
            return self.schedule(0.3)

        state._bump(run.stats, "error_count")
        if outcome == "rejected":
            # Server trả lời bình thường nhưng chưa cho đăng ký (lớp đầy, chưa tới giờ...).
            self.fail_streak = 0
            state._log_deduped(run.run_id, target_id, f"⚠️ {name}: {msg}")
            delay = random.uniform(0.25, 0.5) if run.turbo else random.uniform(0.8, 1.2)
        elif outcome == "timeout":
            # Đã chờ hết timeout rồi: gửi lại gần như ngay để giữ chỗ trong hàng đợi.
            state._bump(run.stats, "timeouts")
            state._log_deduped(run.run_id, target_id, f"⏳ {name}: {msg}")
            delay = random.uniform(0.05, 0.3)
        else:
            # Server trả lỗi nhanh (502/503/429...): lùi dần để không bị chặn IP.
            self.fail_streak += 1
            state._log_deduped(run.run_id, target_id, f"🔥 {name}: {msg}")
            delay = retry_after or _backoff(self.fail_streak, base=0.4, cap=2.0 if run.turbo else 4.0)
        return self.schedule(delay)


_app_states = {}

def get_app_state(user_id="default"):
    if user_id not in _app_states:
        _app_states[user_id] = AppState(user_id)
    return _app_states[user_id]

class AppState:
    def __init__(self, user_id="default"):
        self.user_id = str(user_id)
        # Lưu config theo từng user_id
        if self.user_id == "default":
            self.config_file = os.path.join(os.path.expanduser("~"), ".smartenroll_config.json")
        else:
            self.config_file = os.path.join(os.path.expanduser("~"), f".smartenroll_config_{self.user_id}.json")

        self._is_spamming = False
        self._spam_run = None
        self.spam_thread = None
        self.logs = []
        self.stats = {
            "total_requests": 0,
            "success_count": 0,
            "error_count": 0
        }
        self.is_auto_configuring = False
        self.auto_config_thread = None
        self.auto_config_status = "idle"
        self.last_login_error = ""
        self.session = _new_http_session()
        self.config = None

        # Đồng bộ hóa token giữa các luồng
        self._commit_lock = threading.Lock()      # ghi config/token
        self._relogin_lock = threading.Lock()     # chỉ 1 luồng đăng nhập lại tại một thời điểm
        self._stats_lock = threading.Lock()
        self._log_lock = threading.Lock()
        self._token_gen = 0                       # tăng mỗi lần có token mới
        self._last_login_at = time.time()
        # Kết quả hỏi cổng trường gần nhất: True = còn sống, False = bị từ chối, None = chưa biết
        self.token_ok = None
        self.token_checked_at = None
        self._last_heartbeat_at = 0.0

        # Tiến trình đăng nhập nền (cho web UI)
        self._login_job_lock = threading.Lock()
        self._login_job_stop = None
        self.login_job = {"status": "idle", "attempts": 0, "last_error": ""}

        # Chiến dịch spam
        self._spam_lock = threading.Lock()
        self._spam_run_id = 0
        self._dedupe = {}
        self._spam_relogin_lock = threading.Lock()
        self._spam_relogin_active = False
        self._keepalive_busy = False

        self._migrate_legacy_config()
        self.load_config_data()

        self.registered_classes_schedules = {}
        _live_states.add(self)
        _start_keepalive()
        _background.submit(self._validate_saved_token)

    @property
    def is_spamming(self):
        return self._is_spamming

    @is_spamming.setter
    def is_spamming(self, value):
        # server.py / discord_bot.py dừng spam bằng `state.is_spamming = False`: báo luôn cho chiến dịch.
        self._is_spamming = bool(value)
        run = self._spam_run
        if not value and run is not None:
            run.stop()

    # ------------------------------------------------------------------ config

    def _migrate_legacy_config(self):
        # Chỉ chạy 1 lần lúc khởi động. Bản cũ chạy mỗi lần đọc config, nên vừa đăng xuất
        # xong thì config.json cũ lại bị chép ngược vào và người dùng bị "đăng nhập lại".
        if not os.path.exists(self.config_file) and os.path.exists("config.json"):
            try:
                import shutil
                shutil.copy("config.json", self.config_file)
                self.log(f"Đã tự động di chuyển config.json sang {self.config_file}")
            except Exception as e:
                self.log(f"Lỗi khi di chuyển config.json: {e}")

    def load_config_data(self):
        """Đọc config từ đĩa. KHÔNG gọi mạng: hàm này chạy lúc khởi động và mỗi lần UI hỏi /api/config."""
        if not hasattr(self, '_token_cache'):
            self._token_cache = None
        if not hasattr(self, '_cookie_cache'):
            self._cookie_cache = None
        if not hasattr(self, '_ua_cache'):
            self._ua_cache = None

        if not os.path.exists(self.config_file):
            self.config = None
            return False

        # Đọc file trong khóa: nếu không, một lần đọc chậm có thể ghi đè token vừa đăng nhập xong.
        with self._commit_lock:
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
            except Exception as e:
                # File hỏng: giữ nguyên config trong bộ nhớ, không xóa token đang dùng.
                self.log(f"Lỗi đọc file cấu hình: {e}")
                return self.config is not None

            previous_token = (self.config or {}).get('token')
            self.config = loaded
            if self.config.get('token'):
                self._token_cache = self.config.get('token')
            if self.config.get('cookie'):
                self._cookie_cache = self.config.get('cookie')
            if self.config.get('user_agent'):
                self._ua_cache = self.config.get('user_agent')

            if not self.config.get('token') and self._token_cache:
                self.config['token'] = self._token_cache
            if not self.config.get('cookie') and self._cookie_cache:
                self.config['cookie'] = self._cookie_cache
            if not self.config.get('user_agent') and self._ua_cache:
                self.config['user_agent'] = self._ua_cache

            self.update_session_headers()
            if self.config.get('token') != previous_token:
                self._token_gen += 1
                self.token_ok = None
                self.token_checked_at = None
        return True

    def save_config(self, config_data):
        """Lưu config do người dùng nhập tay và áp dụng ngay."""
        with self._commit_lock:
            self.config = config_data
            self._write_config_file()
            self.update_session_headers()
            self._token_gen += 1
            self.token_ok = None
            self.token_checked_at = None

    def _write_config_file(self):
        # Ghi ra file tạm rồi đổi tên: luồng khác không bao giờ đọc phải file ghi dở.
        tmp_path = self.config_file + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4)
        for _ in range(5):
            try:
                os.replace(tmp_path, self.config_file)
                return
            except PermissionError:
                # Windows: file đích đang được mở đọc ở luồng khác
                time.sleep(0.05)
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4)

    def update_session_headers(self):
        if self.config:
            self.session.headers.update({
                "Authorization": f"Bearer {self.config.get('token', '')}",
                "Cookie": self.config.get('cookie', ''),
                "User-Agent": self.config.get('user_agent') or DEFAULT_UA
            })

    def run_auto_config_bg(self):
        """Dự phòng: mở Chrome để người dùng tự đăng nhập, bắt token rồi lưu vào config của state này."""
        self.is_auto_configuring = True
        self.auto_config_status = "running"
        try:
            captured = get_auto_config()
            if captured and captured.get("token"):
                old = self.config or {}
                merged = dict(old)
                merged.update({k: v for k, v in captured.items() if v})
                for key in ("username", "password", "fb_username", "fb_password"):
                    if old.get(key) and not captured.get(key):
                        merged[key] = old[key]
                self.save_config(merged)
                self.log("✅ Đã lấy token qua Chrome.")
                self.auto_config_status = "success"
            else:
                self.auto_config_status = "failed"
        except Exception as e:
            self.log(f"❌ Lỗi lấy token qua Chrome: {e}")
            self.auto_config_status = "failed"
        finally:
            self.is_auto_configuring = False

    def token_expires_at(self):
        return _jwt_exp((self.config or {}).get("token"))

    def _saved_credentials(self):
        cfg = self.config or {}
        username, password = cfg.get("username"), cfg.get("password")
        if username and password:
            return username, password
        return None

    # ------------------------------------------------------------------ token keep-alive

    def _validate_saved_token(self):
        """Chạy nền lúc khởi động: kiểm tra token đã lưu, hết hạn thì tự đăng nhập lại."""
        creds = self._saved_credentials()
        if not creds:
            return
        exp = self.token_expires_at()
        if exp is not None and exp - time.time() < TOKEN_REFRESH_MARGIN:
            self.log("🔄 Token đã lưu đã/sắp hết hạn. Đang tự động đăng nhập lại...")
            self._refresh_token_if_idle(max_attempts=3)
            return
        self._heartbeat()

    def _heartbeat(self):
        """Gửi 1 request nhẹ bằng token hiện tại để biết cổng trường còn chấp nhận nó không."""
        token = (self.config or {}).get("token")
        if not token:
            return
        self._last_heartbeat_at = time.time()
        seen_gen = self._token_gen
        try:
            resp = self.session.get(DOT_URL, timeout=(CONNECT_TIMEOUT, 20))
        except requests.exceptions.RequestException:
            return  # Cổng trường không phản hồi: chưa kết luận được gì về token.
        if self._token_gen != seen_gen:
            return  # Trong lúc chờ đã có token mới.
        now = time.time()
        if resp.status_code == 200:
            if self.token_ok is False:
                self.log("✅ Cổng trường xác nhận token còn hiệu lực.")
            self.token_ok, self.token_checked_at = True, now
            return
        if resp.status_code != 401:
            return
        self.token_ok, self.token_checked_at = False, now
        iat = _jwt_claims(token).get("iat")
        age = f" (token được cấp {((now - float(iat)) / 60):.0f} phút trước)" if isinstance(iat, (int, float)) else ""
        if self._saved_credentials():
            self.log(f"⚠️ Cổng trường không còn chấp nhận token{age}. Đang đăng nhập lại ngay khi cổng còn vắng...")
            self._recover_from_401(seen_gen, max_attempts=3)
        else:
            self.log(f"⚠️ Cổng trường không còn chấp nhận token{age} và không có mật khẩu đã lưu. Vui lòng đăng nhập lại.")

    def _safe_keepalive_tick(self):
        try:
            self._keepalive_tick()
        except Exception as e:
            self.log(f"⚠️ [Auto-Refresher] Lỗi khi duy trì token: {e}")
        finally:
            self._keepalive_busy = False

    def _keepalive_tick(self):
        if not (self.config or {}).get("token") or self.login_job.get("status") == "running":
            return
        now = time.time()
        if self._saved_credentials():
            exp = self.token_expires_at()
            if exp is not None:
                due = exp - now <= TOKEN_REFRESH_MARGIN
            else:
                due = now - self._last_login_at >= UNKNOWN_EXPIRY_REFRESH_INTERVAL
            if due:
                self.log("🔄 [Auto-Refresher] Token sắp hết hạn, đang gia hạn...")
                if self._refresh_token_if_idle(max_attempts=1):
                    self.log("✅ [Auto-Refresher] Gia hạn token thành công!")
                else:
                    self.log("⚠️ [Auto-Refresher] Chưa gia hạn được, token cũ vẫn được giữ. Sẽ thử lại sau.")
                return
        # Đang spam thì chính các request đăng ký đã đóng vai trò kiểm tra token.
        if not self.is_spamming and now - self._last_heartbeat_at >= HEARTBEAT_INTERVAL:
            self._heartbeat()

    def _refresh_token_if_idle(self, max_attempts):
        creds = self._saved_credentials()
        if not creds or not self._relogin_lock.acquire(blocking=False):
            return False
        try:
            return self._login_loop(creds[0], creds[1], max_attempts=max_attempts)
        finally:
            self._relogin_lock.release()

    # ------------------------------------------------------------------ login

    def _login_attempt(self, username, password):
        """Một lần gọi API đăng nhập trên session RIÊNG.

        Thất bại ở đây không đụng tới token đang dùng (bản cũ xóa sạch cookie/header
        của session chung trước khi đăng nhập, nên một lần gia hạn hỏng là mất luôn token tốt).
        """
        fake_captcha = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))
        headers = {
            "Content-Type": "application/json",
            "User-Agent": DEFAULT_UA,
            "Accept": "application/json, text/plain, */*",
            "Origin": PORTAL,
            "Referer": f"{PORTAL}/login"
        }
        payload = {"username": username, "password": password}
        sess = _new_http_session()
        try:
            try:
                resp = sess.post(
                    LOGIN_URL,
                    params={"g-recaptcha-response": fake_captcha},
                    json=payload,
                    headers=headers,
                    timeout=(CONNECT_TIMEOUT, LOGIN_READ_TIMEOUT),
                    verify=False,
                )
            except requests.exceptions.RequestException as e:
                kind, msg = _describe_exception(e)
                return _LoginAttempt("retry", msg, None, None, kind == "timeout", False)

            if resp.status_code in RETRYABLE_STATUS:
                return _LoginAttempt("retry", f"Cổng trường báo lỗi HTTP {resp.status_code} (quá tải)",
                                     None, _retry_after_seconds(resp), False, False)
            try:
                data = resp.json()
            except ValueError:
                data = None
            if not isinstance(data, dict):
                return _LoginAttempt("retry", f"Cổng trường trả về trang không hợp lệ (HTTP {resp.status_code}, có thể đang quá tải)",
                                     None, None, False, False)

            if resp.status_code == 200 and data.get("success") and data.get("token"):
                cookie_str = "; ".join(f"{k}={v}" for k, v in sess.cookies.items())
                return _LoginAttempt("ok", "", {"token": data["token"], "cookie": cookie_str}, None, False, False)

            message = data.get("message") or f"Portal trả về mã {resp.status_code}"
            if _looks_like_bad_credentials(message):
                return _LoginAttempt("fatal", message, None, None, False, True)
            return _LoginAttempt("retry", message, None, None, False, True)
        finally:
            sess.close()

    def _login_loop(self, username, password, max_attempts=3, should_continue=None, progress=None, wake_event=None):
        """Đăng nhập, thử lại có backoff. max_attempts=None: thử đến khi được / bị dừng / sai mật khẩu."""
        attempt = 0
        last_rejection, same_rejections = None, 0
        while True:
            if should_continue is not None and not should_continue():
                self.last_login_error = "Đã dừng đăng nhập."
                return False
            attempt += 1
            result = self._login_attempt(username, password)

            if result.kind == "ok":
                self._commit_login(username, password, result.data)
                if progress:
                    progress(attempt, "", None)
                return True

            self.last_login_error = result.message
            if result.kind == "fatal":
                self.log(f"❌ Đăng nhập thất bại: {result.message}")
                if progress:
                    progress(attempt, result.message, None)
                return False

            if result.rejected:
                same_rejections = same_rejections + 1 if result.message == last_rejection else 1
                last_rejection = result.message
                if same_rejections >= MAX_IDENTICAL_LOGIN_REJECTIONS:
                    self.log(f"❌ Cổng trường từ chối {same_rejections} lần với cùng thông báo: {result.message}. "
                             "Dừng để tránh khóa tài khoản.")
                    if progress:
                        progress(attempt, result.message, None)
                    return False

            if max_attempts is not None and attempt >= max_attempts:
                self.log(f"❌ Đăng nhập thất bại sau {attempt} lần thử: {result.message}")
                if progress:
                    progress(attempt, result.message, None)
                return False

            if result.timed_out:
                delay = random.uniform(0.2, 1.0)  # đã chờ đủ lâu trong timeout rồi, thử lại ngay
            else:
                delay = result.retry_after or _backoff(attempt - 1)
            self.log(f"⏳ Đăng nhập lần {attempt} chưa được: {result.message}. Thử lại sau {delay:.1f}s...")
            if progress:
                progress(attempt, result.message, delay)
            if not _sleep_unless_stopped(delay, should_continue, wake_event):
                self.last_login_error = "Đã dừng đăng nhập."
                return False

    def _commit_login(self, username, password, data):
        with self._commit_lock:
            old = self.config or {}
            self.config = {
                "api_url": f"{PORTAL}/coursesregistration",
                "token": data["token"],
                "cookie": data["cookie"],
                "id_dot": old.get("id_dot") or "76",
                "user_agent": DEFAULT_UA,
                "username": username,
                "password": password,
                "fb_username": old.get("fb_username", ""),
                "fb_password": old.get("fb_password", "")
            }
            self._token_cache = data["token"]
            self._cookie_cache = data["cookie"]
            self._write_config_file()
            self.update_session_headers()
            self._token_gen += 1
            self._last_login_at = time.time()
            self._last_heartbeat_at = self._last_login_at  # vừa đăng nhập: chưa cần hỏi lại cổng trường
            self.token_ok = True
            self.token_checked_at = self._last_login_at
        self.last_login_error = ""
        self.log(f"🔑 Đăng nhập thành công tài khoản: {username}!")
        # Không bắt người dùng chờ: token đã dùng được ngay, đợt đăng ký cập nhật sau.
        # Đang spam (= đang giờ cao điểm) thì bỏ qua, khỏi gửi thêm request không cần cho việc đăng ký.
        if not self._is_spamming:
            _background.submit(self._refresh_latest_dot)

    def _refresh_latest_dot(self):
        try:
            resp = self.request_with_retry("GET", DOT_URL, timeout=15, retries=3, relogin=False)
            if resp.status_code != 200:
                return
            body = resp.json()
            dot_data = body.get('data') or body.get('body') or []
            dot_ids = [str(d.get('id') or d.get('idDot')) for d in dot_data if d.get('id') or d.get('idDot')]
            if not dot_ids:
                return
            latest_dot = dot_ids[0]
            with self._commit_lock:
                if self.config and self.config.get("id_dot") != latest_dot:
                    self.config["id_dot"] = latest_dot
                    self._write_config_file()
                    changed = True
                else:
                    changed = False
            if changed:
                self.log(f"📅 Tự động quét và cấu hình ID Đợt học mới nhất: {latest_dot}")
        except Exception as e:
            self.log(f"⚠️ Chưa lấy được đợt đăng ký mới nhất (dùng đợt đã lưu): {e}")

    def login_with_credentials(self, username, password, max_attempts=3):
        """Đăng nhập đồng bộ (Discord bot, export...). Trả về True/False, lỗi ở self.last_login_error."""
        with self._relogin_lock:
            return self._login_loop(username, password, max_attempts=max_attempts)

    def start_login_job(self, username, password, persistent=True):
        """Đăng nhập nền cho web UI: thử lại liên tục đến khi vào được (persistent) hoặc tối đa 3 lần."""
        with self._login_job_lock:
            if self.login_job.get("status") == "running":
                if self.login_job.get("username") == username:
                    return True, "attached"
                return False, "Đang có tiến trình đăng nhập cho tài khoản khác. Hãy dừng nó trước."
            stop = threading.Event()
            self._login_job_stop = stop
            self.login_job = {
                "status": "running",
                "username": username,
                "persistent": persistent,
                "attempts": 0,
                "last_error": "",
                "started_at": time.time(),
                "next_retry_at": None,
            }
        threading.Thread(target=self._login_job_worker, args=(username, password, persistent, stop), daemon=True).start()
        return True, "started"

    def stop_login_job(self):
        with self._login_job_lock:
            if self._login_job_stop is not None:
                self._login_job_stop.set()
            if self.login_job.get("status") == "running":
                self.login_job = dict(self.login_job, status="stopped", next_retry_at=None)

    def _login_job_worker(self, username, password, persistent, stop):
        def is_current():
            return self._login_job_stop is stop

        def should_continue():
            return is_current() and not stop.is_set()

        def progress(attempt, message, delay):
            if is_current() and not stop.is_set():
                self.login_job = dict(self.login_job, attempts=attempt, last_error=message,
                                      next_retry_at=(time.time() + delay) if delay else None)

        ok = False
        # Chờ nếu một luồng khác (spam/refresher) đang đăng nhập lại, nhưng vẫn dừng được.
        while should_continue():
            if self._relogin_lock.acquire(timeout=0.5):
                try:
                    ok = self._login_loop(username, password,
                                          max_attempts=None if persistent else 3,
                                          should_continue=should_continue, progress=progress,
                                          wake_event=stop)
                finally:
                    self._relogin_lock.release()
                break

        with self._login_job_lock:
            if not is_current() or self.login_job.get("status") != "running":
                return
            if ok:
                status = "success"
            elif stop.is_set():
                status = "stopped"
            else:
                status = "failed"
            self.login_job = dict(self.login_job, status=status, next_retry_at=None,
                                  finished_at=time.time(),
                                  last_error="" if ok else self.last_login_error)

    def _recover_from_401(self, seen_gen, should_continue=None, max_attempts=3, wake_event=None):
        """Xử lý 401 kiểu single-flight: chỉ một luồng đăng nhập lại, các luồng khác chờ token mới.

        seen_gen là thế hệ token lúc gửi request bị 401; nếu token đã đổi thì chỉ cần gửi lại.
        """
        while True:
            if self._token_gen != seen_gen:
                return True
            if should_continue is not None and not should_continue():
                return False
            if self._relogin_lock.acquire(timeout=0.5):
                try:
                    if self._token_gen != seen_gen:
                        return True
                    self.token_ok, self.token_checked_at = False, time.time()
                    creds = self._saved_credentials()
                    if not creds:
                        self.last_login_error = "Không có mật khẩu đã lưu để tự đăng nhập lại."
                        return False
                    self.log("🔄 Token bị từ chối (401). Đang đăng nhập lại...")
                    return self._login_loop(creds[0], creds[1], max_attempts=max_attempts,
                                            should_continue=should_continue, wake_event=wake_event)
                finally:
                    self._relogin_lock.release()

    # ------------------------------------------------------------------ HTTP

    def request_with_retry(self, method, url, retries=2, relogin=True, **kwargs):
        """Gọi API cổng trường: timeout chịu tải, thử lại khi quá tải, tự đăng nhập lại khi 401."""
        kwargs["timeout"] = _normalize_timeout(kwargs.get("timeout"))
        idempotent = method.upper() in ("GET", "HEAD", "OPTIONS", "DELETE", "PUT")
        attempt = 0
        relogged = False
        while True:
            seen_gen = self._token_gen
            try:
                resp = self.session.request(method, url, **kwargs)
            except requests.exceptions.RequestException as e:
                safe_to_retry = idempotent or isinstance(e, requests.exceptions.ConnectTimeout)
                if attempt >= retries or not safe_to_retry:
                    raise
                attempt += 1
                kind, _ = _describe_exception(e)
                time.sleep(random.uniform(0.2, 1.0) if kind == "timeout" else _backoff(attempt))
                continue

            if resp.status_code == 401 and relogin and not relogged:
                relogged = True
                deadline = time.time() + 120
                if self._recover_from_401(seen_gen, should_continue=lambda: time.time() < deadline):
                    if kwargs.get("headers") and "Authorization" in kwargs["headers"]:
                        kwargs["headers"]["Authorization"] = f"Bearer {self.config['token']}"
                    continue
                return resp

            if resp.status_code in RETRYABLE_STATUS and attempt < retries:
                attempt += 1
                time.sleep(_retry_after_seconds(resp) or _backoff(attempt))
                continue
            return resp

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        try:
            print(log_entry)
        except (UnicodeEncodeError, OSError, ValueError):
            pass  # console Windows không in được emoji / không có console: bỏ qua, không làm hỏng luồng gọi
        with self._log_lock:
            self.logs.append(log_entry)
            if len(self.logs) > 300:
                del self.logs[:len(self.logs) - 300]

    def fetch_class_detail(self, class_id, is_conditional=False):
        if is_conditional:
            url = f"{PORTAL}/api/v1/dkhpdk/getLopHocPhanDetail"
        else:
            url = f"{PORTAL}/api/v1/dkhp/getLopHocPhanDetail"
        params = {"idLopHocPhan": class_id}
        try:
            resp = self.request_with_retry("GET", url, params=params, timeout=20, retries=2)
            if resp.status_code == 200:
                return resp.json().get('body') or []
        except Exception:
            pass
        return None

    def format_schedule(self, details):
        if not details:
            return "⚠️ Không lấy được lịch"
        parts = []
        for d in details:
            raw_thu = str(d.get('thu', ''))
            thu_text = "Chủ Nhật" if raw_thu in ['8', 'CN', 'Chủ Nhật'] else f"Thứ {raw_thu}"
            tiet = d.get('tietHoc', '?')
            phong = d.get('phong') or d.get('tenPhong') or ""
            phong_text = f" - P.{phong}" if phong else ""
            parts.append(f"{thu_text} (Tiết {tiet}){phong_text}")
        return " | ".join(parts)

    def parse_periods(self, tiet_str):
        periods = set()
        if not tiet_str:
            return periods
        tiet_str = str(tiet_str)
        parts = tiet_str.split(',')
        for part in parts:
            part = part.strip()
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    periods.update(range(start, end + 1))
                except Exception:
                    pass
            else:
                try:
                    periods.add(int(part))
                except Exception:
                    pass
        return periods

    def get_conflict_details(self, details_a):
        # Checks if details_a (scanned class) conflicts with any registered classes
        # Returns a dict: {"conflicting": True, "conflict_with": "Môn B [Lớp Y]"} or {"conflicting": False}
        if not details_a or not self.registered_classes_schedules:
            return {"conflicting": False}
            
        for sa in details_a:
            thu_a = str(sa.get("thu", ""))
            periods_a = self.parse_periods(sa.get("tietHoc", ""))
            if not thu_a or not periods_a:
                continue
                
            for rc_id, info in self.registered_classes_schedules.items():
                rc_name = info.get("name", "Môn học đã đăng ký")
                rc_code = info.get("code", "")
                rc_schedules = info.get("schedules", [])
                
                for sb in rc_schedules:
                    thu_b = str(sb.get("thu", ""))
                    periods_b = self.parse_periods(sb.get("tietHoc", ""))
                    if not thu_b or not periods_b:
                        continue
                        
                    if thu_a == thu_b:
                        if periods_a.intersection(periods_b):
                            return {
                                "conflicting": True,
                                "conflict_with": f"{rc_name} (Lớp {rc_code})"
                            }
        return {"conflicting": False}

    def check_filter(self, details, target_thu, target_ca):
        if not details:
            return False
        if target_thu == "Tất cả" and target_ca == "Tất cả":
            return True
        for d in details:
            raw_thu = str(d.get('thu', ''))
            is_cn = raw_thu in ['8', 'CN', 'Chủ Nhật']
            current_thu = "Chủ nhật" if is_cn else f"Thứ {raw_thu}"
            
            match_thu = (target_thu == "Tất cả") or (target_thu.lower() == current_thu.lower())
            match_ca = (target_ca == "Tất cả")
            
            if target_ca != "Tất cả":
                tiet_str = d.get('tietHoc', '')
                t_s, t_e = CA_HOC[target_ca][0], CA_HOC[target_ca][-1]
                if f"{t_s}-{t_e}" in tiet_str or f"{t_s},{t_e}" in tiet_str:
                    match_ca = True
                else:
                    try:
                        if '-' in tiet_str:
                            start, end = map(int, tiet_str.split('-'))
                            if t_s <= start <= t_e:
                                match_ca = True
                    except Exception:
                        pass
            if match_thu and match_ca:
                return True
        return False

    # ------------------------------------------------------------------ đăng ký (spam)

    def _bump(self, stats, key, amount=1):
        with self._stats_lock:
            stats[key] = stats.get(key, 0) + amount

    def _log_deduped(self, run_id, target_id, message):
        """Gộp các thông báo lặp lại (vd 'Lớp đã đủ') để log không bị trôi mất dòng quan trọng."""
        key = (run_id, target_id)
        with self._stats_lock:
            last, count = self._dedupe.get(key, (None, 0))
            count = count + 1 if message == last else 1
            self._dedupe[key] = (message, count)
        if count == 1:
            self.log(message)
        elif count % 10 == 0:
            self.log(f"{message} (lặp lại x{count})")

    def _register_once(self, t):
        """Gửi 1 request đăng ký. Trả về (kết quả, thông báo, retry_after).

        kết quả: success | already | rejected | expired | timeout | overloaded
        """
        if t.get('is_conditional', False):
            url = f"{PORTAL}/api/v1/dkhpdk/dangKyLopHocPhan"
        else:
            url = f"{PORTAL}/api/v1/dkhp/dangKyLopHocPhan"
        params = {
            "idLopHocPhan": str(t['id']),
            "g-recaptcha-response": ""
        }
        try:
            resp = self.session.post(url, params=params, timeout=(CONNECT_TIMEOUT, REGISTER_READ_TIMEOUT))
        except requests.exceptions.RequestException as e:
            kind, msg = _describe_exception(e)
            return ("timeout" if kind == "timeout" else "overloaded"), msg, None

        if resp.status_code == 401:
            return "expired", "Token hết hạn (401)", None
        if resp.status_code != 200:
            return "overloaded", f"Cổng trường báo lỗi HTTP {resp.status_code}", _retry_after_seconds(resp)
        try:
            d = resp.json()
        except ValueError:
            d = None
        if not isinstance(d, dict):
            return "overloaded", "Cổng trường trả về trang không hợp lệ (có thể đang quá tải)", None

        msg = _nfc(d.get("message", ""))
        if d.get("success"):
            return "success", msg, None
        if "đã đăng ký" in msg or "Trùng lịch học" in msg:
            return "already", msg, None
        return "rejected", msg or "Cổng trường từ chối (không kèm thông báo)", None

    def _abort_run(self, run, message):
        """Dừng hẳn một chiến dịch (vd: không còn cách nào đăng nhập lại)."""
        with self._spam_lock:
            first = not run.aborted
            run.aborted = True
            if self._spam_run is run:
                self._is_spamming = False
        run.stop()
        if first:
            self.log(message)

    def _begin_spam_relogin(self, seen_gen, run):
        """Single-flight cho các làn spam: chỉ MỘT luồng đăng nhập lại, các làn khác hẹn giờ kiểm tra lại.

        Trả về "ready" (đã có token mới), "pending" (đang đăng nhập lại) hoặc "no_credentials".
        """
        with self._spam_relogin_lock:
            if self._token_gen != seen_gen:
                return "ready"
            if self._spam_relogin_active:
                return "pending"
            if not self._saved_credentials():
                self.last_login_error = "Không có mật khẩu đã lưu để tự đăng nhập lại."
                return "no_credentials"
            self._spam_relogin_active = True
        threading.Thread(target=self._spam_relogin_worker, args=(seen_gen, run),
                         name=f"smartenroll-relogin-{self.user_id}", daemon=True).start()
        return "pending"

    def _spam_relogin_worker(self, seen_gen, run):
        try:
            ok = self._recover_from_401(seen_gen, should_continue=run.active, max_attempts=None,
                                        wake_event=run.stop_event)
            if not ok and run.active():
                self._abort_run(run, f"💀 Không tự đăng nhập lại được ({self.last_login_error}). "
                                     "Dừng spam, vui lòng đăng nhập lại.")
        except Exception as e:
            self._abort_run(run, f"💀 Lỗi khi tự đăng nhập lại: {e}. Dừng spam, vui lòng đăng nhập lại.")
        finally:
            with self._spam_relogin_lock:
                self._spam_relogin_active = False

    def run_spam_loop(self, targets, mode="normal"):
        """Chạy chiến dịch đăng ký; trả về khi mọi lớp đã xong hoặc khi bị dừng (is_spamming = False).

        Mỗi lớp 1 làn (Turbo: 3 làn). Làn không giữ luồng riêng mà chạy trên bộ hẹn giờ dùng chung,
        nên luồng gọi hàm này chỉ ngồi chờ một Event, không tốn CPU.
        """
        turbo = mode == "turbo"
        lanes_per_class = TURBO_LANES_PER_CLASS if turbo else 1
        with self._spam_lock:
            previous = self._spam_run
            self._spam_run_id += 1
            run = _SpamRun(self, self._spam_run_id, turbo)
            self._spam_run = run
            self._is_spamming = True
            self._dedupe = {}
            self.stats = run.stats
        if previous is not None:
            previous.stop()
        self.log(f"🔥 Bắt đầu chiến dịch Spam {len(targets)} lớp ở chế độ {mode.upper()} "
                 f"({lanes_per_class} luồng/lớp, timeout đọc {REGISTER_READ_TIMEOUT}s)...")

        lanes = []
        for t in targets:
            done = threading.Event()
            lanes.extend(_SpamLane(run, t, done) for _ in range(lanes_per_class))
        run.lanes_left = len(lanes)
        if not lanes:
            run.finished.set()
        delay = 0.0
        for lane in lanes:
            lane.schedule(delay)
            delay += random.uniform(0.05, 0.2)  # rải thời điểm bắt đầu để các làn không bắn cùng một nhịp

        run.finished.wait()

        with self._spam_lock:
            current = self._spam_run is run
            finished_all = current and not run.stop_event.is_set()
            if current:
                self._is_spamming = False
        run.stop()  # làn nào còn đang hẹn giờ sẽ tự kết thúc khi tới lượt
        if finished_all:
            self.log("✅ Đã xử lý xong toàn bộ lớp trong danh sách.")
        self.log("⏹ Đã dừng Spam.")
