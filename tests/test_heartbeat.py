"""Giữ phiên khi treo máy: heartbeat phát hiện token bị cổng trường hủy và đăng nhập lại sớm.

Chạy:  venv/bin/python tests/test_heartbeat.py
Không có mạng thật: mọi request tới cổng trường đi vào cổng giả trong tests/fakes.py.
"""
from fakes import *  # noqa: F401,F403  (phải import đầu tiên: cô lập HOME, thay HTTP bằng cổng giả)
from fakes import PORTAL, check, finish, jwt, wait_for, wait_quiet, write_cfg, core_state
import threading
import time
import json
import os

# 1. startup heartbeat: portal accepts token -> token_ok True
PORTAL.script("getDot", "ok")
write_cfg("h1", jwt(30 * 86400, "old"))
st = core_state.AppState("h1")
check(st.token_ok is None or st.token_ok is True, "token status starts unknown/true")
check(wait_for(lambda: st.token_ok is True, 3), "startup heartbeat: portal confirms token -> token_ok True")
check(st.token_checked_at and time.time() - st.token_checked_at < 5, "checked_at recorded")

# 2. portal drops token server-side (JWT still 'valid' by date) -> detect + relogin early
PORTAL.calls = {}
PORTAL.script("getDot", "unauth", "ok")
PORTAL.script("login", "ok")
old_token = st.config["token"]
st._heartbeat()
check(PORTAL.calls.get("login") == 1, "401 on heartbeat triggers one relogin")
check(st.config["token"] != old_token and st.token_ok is True, "fresh token in place and marked ok")
check(any("phút trước" in l for l in st.logs), "log records how old the dropped token was")

# 3. portal not answering -> no conclusion, status unchanged
PORTAL.script("getDot", "connect_timeout")
before = (st.token_ok, st.token_checked_at)
st._heartbeat()
check((st.token_ok, st.token_checked_at) == before, "timeout leaves token status unchanged")

# 4. keepalive tick paces heartbeats and skips while spamming
# (first let background threads from earlier steps finish, e.g. the period refresh that follows a relogin,
#  so they can't add their own getDot calls to this count)
wait_quiet()
PORTAL.calls = {}
PORTAL.script("getDot", "ok")
st._last_heartbeat_at = 0
st.is_spamming = True
st._keepalive_tick()
check(PORTAL.calls.get("getDot", 0) == 0, "no heartbeat while spamming")
st.is_spamming = False
st._keepalive_tick()
st._keepalive_tick()
check(PORTAL.calls.get("getDot", 0) == 1, "one heartbeat, then waits HEARTBEAT_INTERVAL")

# 5. no saved password -> marked bad, no login attempt
write_cfg("h2", jwt(30 * 86400, "x"), with_creds=False)
PORTAL.calls = {}
PORTAL.script("getDot", "unauth")
st2 = core_state.AppState("h2")
st2._heartbeat()
check(st2.token_ok is False and PORTAL.calls.get("login", 0) == 0, "no credentials: token marked bad, no login spam")

finish()
