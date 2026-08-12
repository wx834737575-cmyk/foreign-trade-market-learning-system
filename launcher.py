from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from scripts.backup_data import create_backup


ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
DATA = ROOT / "data"
HEALTH_URL = "http://127.0.0.1:8000/api/health"
DASHBOARD_URL = "http://127.0.0.1:8000/"


def is_healthy() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=1.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return response.status == 200 and payload.get("status") == "ok"
    except (OSError, ValueError, urllib.error.URLError):
        return False


def resolve_python() -> Path:
    candidates = [
        BACKEND / ".runtime" / "Scripts" / "pythonw.exe",
        BACKEND / ".runtime" / "Scripts" / "python.exe",
        BACKEND / ".venv" / "Scripts" / "pythonw.exe",
        BACKEND / ".venv" / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("尚未安装本地运行环境，请先双击 scripts\\首次安装.cmd")


def start_server() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    logs = DATA / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    log_file = (logs / "dashboard.log").open("a", encoding="utf-8")
    creation_flags = 0
    if os.name == "nt":
        creation_flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    process = subprocess.Popen(
        [str(resolve_python()), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=BACKEND,
        stdin=subprocess.DEVNULL,
        stdout=log_file,
        stderr=log_file,
        creationflags=creation_flags,
        close_fds=True,
    )
    (DATA / "dashboard.pid").write_text(str(process.pid), encoding="ascii")


def main() -> int:
    if not is_healthy():
        try:
            create_backup(ROOT, daily=True)
            start_server()
        except Exception as exc:
            print(f"启动失败：{exc}", file=sys.stderr)
            return 1
        for _ in range(40):
            if is_healthy():
                break
            time.sleep(0.25)
        else:
            print(f"本地服务未能启动，请查看 {DATA / 'logs' / 'dashboard.log'}", file=sys.stderr)
            return 2
    webbrowser.open(DASHBOARD_URL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
