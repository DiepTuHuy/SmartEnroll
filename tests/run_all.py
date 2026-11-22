#!/usr/bin/env python3
"""Chạy toàn bộ test chức năng (mỗi file một tiến trình riêng). Load test chạy riêng: tests/load_test.py"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS = ["test_overload.py", "test_heartbeat.py", "test_flask_api.py"]

failed = []
for name in TESTS:
    print(f"\n===== {name}", flush=True)
    if subprocess.run([sys.executable, str(HERE / name)], cwd=HERE).returncode != 0:
        failed.append(name)
print("\n" + ("TẤT CẢ ĐỀU QUA" if not failed else f"LỖI: {failed}"))
sys.exit(1 if failed else 0)
