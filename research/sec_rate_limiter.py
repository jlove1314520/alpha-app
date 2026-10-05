# -*- coding: utf-8 -*-
"""跨行程共用的 SEC 發送限速器（先.二十-一，總司令 2026-10-05 裁示）。

裁示原文：「兩個並行工作各自標〔互動視窗執行中〕，**合計**對 SEC 的請求仍不得超過
每秒 5 次（**共用同一個全域限速器**）。」

為什麼需要這個檔：原本 `us_universe_rebuild.py` 的限速器是**行程內**的
（`threading.Lock` ＋ 一個 list 變數）。單一行程跑時完全正確，但兩個 Python 行程
並行時，各自以為自己可以用滿 5 req/秒，合計就是 10 req/秒——剛好等於 SEC 官方上限、
失去原本「取官方上限一半」的安全邊際。這正是 CLAUDE.md 三之三反覆講的那種形狀：
每個元件各自正確運作，合起來卻違反了約束。

做法：用檔案當共用狀態。每次發送前，以作業系統層級的互斥（獨佔建立 .lock 檔）
讀出「下一個可發送時刻」，往後推 1/RATE 秒再寫回，然後睡到那個時刻。
時間戳用 `time.time()`（牆鐘），因為 `time.monotonic()` 的原點在不同行程之間不可比。

守門員原則（CLAUDE.md 十二）：這個限速器自己壞掉（檔案讀寫失敗、鎖搶不到）時，
**退回成「本行程至少睡 1/RATE 秒」**，絕不讓呼叫端中斷或無限等待——
寧可偶爾比目標慢一點或快一點，不可把整條抓取流程卡死。
"""
from __future__ import annotations

import os
import time
from pathlib import Path

STATE = Path(__file__).resolve().parent / "data" / "raw" / ".sec_rate_slot"
LOCK = Path(str(STATE) + ".lock")
RATE_PER_SEC = 5.0
INTERVAL = 1.0 / RATE_PER_SEC
_LOCK_STALE_SEC = 5.0


def _acquire_file_lock(timeout: float = 2.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            fd = os.open(str(LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except FileExistsError:
            try:
                # 持鎖者當掉會留下孤兒鎖；超過門檻就視為陳舊並清掉
                if time.time() - LOCK.stat().st_mtime > _LOCK_STALE_SEC:
                    LOCK.unlink(missing_ok=True)
                    continue
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.005)
        except Exception:  # noqa: BLE001
            return False
    return False


def _release_file_lock() -> None:
    try:
        LOCK.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass


def acquire_slot() -> None:
    """取得一個發送額度；必要時睡到可以發送的時刻。全行程合計 ≤ RATE_PER_SEC。"""
    STATE.parent.mkdir(parents=True, exist_ok=True)
    target = None
    if _acquire_file_lock():
        try:
            now = time.time()
            prev = 0.0
            try:
                prev = float(STATE.read_text(encoding="utf-8").strip() or 0.0)
            except Exception:  # noqa: BLE001
                prev = 0.0
            target = max(now, prev)
            STATE.write_text(f"{target + INTERVAL:.6f}", encoding="utf-8")
        except Exception:  # noqa: BLE001
            target = None
        finally:
            _release_file_lock()
    if target is None:
        # fail open：共用狀態不可用時，至少維持本行程的最低間隔，不中斷呼叫端
        time.sleep(INTERVAL)
        return
    d = target - time.time()
    if d > 0:
        time.sleep(d)
