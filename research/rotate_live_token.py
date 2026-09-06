# -*- coding: utf-8 -*-
"""一鍵更換 live server 的 X-Alpha-Local-Token（2026-09-06 連線三.6）。

**什麼時候該換**
- 手機遺失或被別人拿走（token 存在手機的 localStorage 裡）
- 懷疑 token 外洩：貼到截圖／訊息／公開頻道裡、或給過別人看
- `/security` 顯示 401 次數異常升高（有人在猜）
- 換過人、換過裝置、或只是定期輪替（建議每季一次）

**做完會怎樣**
舊 token 立即失效——所有帶舊 token 的請求會變成 401。手機端要重新貼一次新 token，
在 App 設定頁的「X-Alpha-Local-Token」欄位。

用法：
    python research/rotate_live_token.py            # 換新並印出
    python research/rotate_live_token.py --show     # 只看目前的，不換
"""
from __future__ import annotations

import secrets
import subprocess
import sys
import time
from pathlib import Path

TOKEN_PATH = Path(__file__).resolve().parent / ".alpha_live_token"
PID_PATH = Path(__file__).resolve().parent / ".alpha_live_server.pid"


def current() -> str | None:
    if not TOKEN_PATH.exists():
        return None
    try:
        return TOKEN_PATH.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def restart_server() -> str:
    """殺掉現有行程；排程（AlphaLiveServer，每分鐘檢查）會在 1 分鐘內自動拉起。

    為什麼不自己重新啟動：啟動流程在 run-alpha-live-server-cycle.ps1 裡（要設環境變數、
    導 log、寫 PID 檔），在這裡再寫一份等於維護兩套會走鐘的啟動邏輯。殺掉就好，
    讓既有的常駐機制接手。
    """
    pid = None
    if PID_PATH.exists():
        try:
            pid = int(PID_PATH.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            pid = None
    if pid is None:
        return "找不到 PID 檔，請自行重啟 alpha_live_server.py（或等排程 1 分鐘內拉起）"
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                       capture_output=True, check=False, timeout=20)
        return f"已終止舊行程 PID {pid}，排程會在 1 分鐘內用新 token 重新啟動"
    except (OSError, subprocess.SubprocessError) as e:
        return f"終止行程失敗（{type(e).__name__}: {e}），請自行重啟"


def main() -> int:
    if "--show" in sys.argv:
        tok = current()
        print(f"目前 token：{tok}" if tok else "目前沒有 token 檔（伺服器第一次啟動時會自動產生）")
        return 0

    old = current()
    new = secrets.token_urlsafe(24)
    try:
        TOKEN_PATH.write_text(new, encoding="utf-8")
    except OSError as e:
        print(f"寫入失敗：{e}")
        return 1

    print("=" * 66)
    print("  已更換 live server token")
    print("=" * 66)
    if old:
        print(f"  舊 token（已失效）：{old[:6]}…{old[-4:]}")
    print(f"  新 token：{new}")
    print()
    print("  接下來要做的事：")
    print("   1. 手機開 Alpha → 設定 → 即時伺服器 → X-Alpha-Local-Token 貼上新的")
    print("   2. 按「測試連線」，看到「連線成功」才算完成")
    print("   3. 其他有貼過舊 token 的裝置也要一起換，否則會一直 401")
    print()
    print(f"  {restart_server()}")
    print("=" * 66)
    # 伺服器是在啟動時讀 token 的，所以一定要重啟才會生效
    time.sleep(1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
