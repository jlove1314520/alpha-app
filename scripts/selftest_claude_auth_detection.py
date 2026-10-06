# -*- coding: utf-8 -*-
"""先.十四-一自測：注入假錯誤字串／假時間戳，驗證「本機Claude需要重新登入」這條
偵測鏈（classify → heartbeat record → check_local_schedule_heartbeat 彙整）的每一段
都真的認得出來，而不是只看過程式碼就假設它會動。

不碰真正的 research/data/claude_launcher_heartbeat.json（用暫存目錄＋monkeypatch
路徑常數），跑完清乾淨，不留任何痕跡在正式檔案裡。

用法：python scripts/selftest_claude_auth_detection.py
"""
from __future__ import annotations

import importlib
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import claude_auth_classifier as cac  # noqa: E402

FAIL = []


def check(name, cond, detail=""):
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAIL.append(name)


def test_classifier():
    cases = [
        ("You are not currently logged in. Run `claude login` to continue.", "AUTH_EXPIRED"),
        ("Error: Login expired, please re-authenticate.", "AUTH_EXPIRED"),
        ("session expired, please log in again", "AUTH_EXPIRED"),
        ("anthropic.APIStatusError: authentication_error", "AUTH_EXPIRED"),
        ("You have exceeded your usage limit for this period.", "QUOTA_EXCEEDED"),
        ("rate_limit_error: 429 too many requests", "QUOTA_EXCEEDED"),
        ("Your credit balance is too low to access the Anthropic API", "QUOTA_EXCEEDED"),
        ("some totally unrelated python traceback: ZeroDivisionError", "OK"),
        ("", "OK"),
    ]
    for text, expected in cases:
        got = cac.classify_text(text)["status"]
        check(f"classify_text: {text[:40]!r} -> {expected}", got == expected, f"實際={got}")
    # 讀不存在的檔案：不得拋例外，必須回 UNKNOWN
    res = cac.classify_file(str(ROOT / "__definitely_not_exists__.jsonl"))
    check("classify_file 讀不存在的檔案 -> UNKNOWN（不拋例外）", res["status"] == "UNKNOWN", str(res))


def test_heartbeat_recorder(tmpdir: Path):
    import update_claude_launcher_heartbeat as uh
    importlib.reload(uh)
    uh.PATH = tmpdir / "claude_launcher_heartbeat.json"

    rec = uh.record("devqueue", "20270101-000000", "OK", "測試正常一輪")
    check("record OK 後 last_ok_at 與 last_attempt_at 皆有值",
          bool(rec.get("last_ok_at")) and bool(rec.get("last_attempt_at")))

    rec2 = uh.record("marathon", "20270101-000100", "QUEUE_EMPTY", "佇列空")
    check("record QUEUE_EMPTY 不應更新 last_attempt_at（不算嘗試執行）",
          "last_attempt_at" not in rec2)

    rec3 = uh.record("hypothesis_queue", "20270101-000200", "AUTH_EXPIRED", "login expired 偵測到")
    check("record AUTH_EXPIRED 應更新 last_attempt_at 但不應有 last_ok_at",
          bool(rec3.get("last_attempt_at")) and "last_ok_at" not in rec3)

    doc = json.loads(uh.PATH.read_text(encoding="utf-8"))
    check("三個 launcher 都寫進同一份檔案", set(doc.keys()) == {"devqueue", "marathon", "hypothesis_queue"}, str(doc.keys()))


def test_aggregator(tmpdir: Path):
    import check_local_schedule_heartbeat as hb
    importlib.reload(hb)
    hb.CLAUDE_AUTH_PATH = tmpdir / "claude_launcher_heartbeat.json"
    now = datetime.now(timezone.utc)

    # 情境一：全部正常
    fresh = now.astimezone().isoformat(timespec="seconds")
    hb.CLAUDE_AUTH_PATH.write_text(json.dumps({
        "devqueue": {"last_reason": "OK", "last_attempt_at": fresh, "last_ok_at": fresh},
        "marathon": {"last_reason": "OK", "last_attempt_at": fresh, "last_ok_at": fresh},
        "hypothesis_queue": {"last_reason": "OK", "last_attempt_at": fresh, "last_ok_at": fresh},
    }, ensure_ascii=False), encoding="utf-8")
    r = hb._evaluate_claude_auth(now)
    check("情境一：全部正常 -> overall_status=OK", r["overall_status"] == "OK", str(r))

    # 情境二：devqueue 偵測到 AUTH_EXPIRED
    hb.CLAUDE_AUTH_PATH.write_text(json.dumps({
        "devqueue": {"last_reason": "AUTH_EXPIRED", "last_attempt_at": fresh, "last_detail": "login expired"},
        "marathon": {"last_reason": "OK", "last_attempt_at": fresh, "last_ok_at": fresh},
        "hypothesis_queue": {"last_reason": "OK", "last_attempt_at": fresh, "last_ok_at": fresh},
    }, ensure_ascii=False), encoding="utf-8")
    r = hb._evaluate_claude_auth(now)
    check("情境二：devqueue AUTH_EXPIRED -> overall_status=AUTH_EXPIRED", r["overall_status"] == "AUTH_EXPIRED", str(r))

    # 情境三：marathon 連續 8 小時沒有嘗試執行（超過7小時門檻，先.二十八）-> STALLED_3H
    stale = (now - timedelta(hours=8)).astimezone().isoformat(timespec="seconds")
    hb.CLAUDE_AUTH_PATH.write_text(json.dumps({
        "devqueue": {"last_reason": "OK", "last_attempt_at": fresh, "last_ok_at": fresh},
        "marathon": {"last_reason": "ERROR", "last_attempt_at": stale},
        "hypothesis_queue": {"last_reason": "QUEUE_EMPTY", "last_attempt_at": stale},
    }, ensure_ascii=False), encoding="utf-8")
    r = hb._evaluate_claude_auth(now)
    check("情境三：marathon 8小時無嘗試 -> overall_status=STALLED_3H", r["overall_status"] == "STALLED_3H", str(r))

    # 情境三之二（先.二十八）：marathon／hypothesis_queue 5 小時無嘗試（每 6 小時一輪的正常間隔）不得誤報
    mid = (now - timedelta(hours=5)).astimezone().isoformat(timespec="seconds")
    hb.CLAUDE_AUTH_PATH.write_text(json.dumps({
        "devqueue": {"last_reason": "OK", "last_attempt_at": fresh, "last_ok_at": fresh},
        "marathon": {"last_reason": "OK", "last_attempt_at": mid, "last_ok_at": mid},
        "hypothesis_queue": {"last_reason": "OK", "last_attempt_at": mid, "last_ok_at": mid},
    }, ensure_ascii=False), encoding="utf-8")
    r = hb._evaluate_claude_auth(now)
    check("情境三之二：研究線 5小時無嘗試 -> 仍 OK（7小時門檻）", r["overall_status"] == "OK", str(r))

    # 情境四：心跳檔不存在 -> UNKNOWN，不拋例外
    missing_path = tmpdir / "__no_such_file__.json"
    hb.CLAUDE_AUTH_PATH = missing_path
    r = hb._evaluate_claude_auth(now)
    check("情境四：心跳檔不存在 -> UNKNOWN（不拋例外）", r["overall_status"] == "UNKNOWN", str(r))

    # 情境五：心跳檔內容是壞 JSON -> UNKNOWN，不拋例外（守門員自己失敗只能降級）
    bad_path = tmpdir / "bad.json"
    bad_path.write_text("{not valid json", encoding="utf-8")
    hb.CLAUDE_AUTH_PATH = bad_path
    r = hb._evaluate_claude_auth(now)
    check("情境五：心跳檔是壞JSON -> UNKNOWN（不拋例外）", r["overall_status"] == "UNKNOWN", str(r))


def main() -> int:
    print("=== 測試一：claude_auth_classifier.py 字串分類 ===")
    test_classifier()
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        print("\n=== 測試二：update_claude_launcher_heartbeat.py 記錄邏輯 ===")
        test_heartbeat_recorder(tmpdir)
        print("\n=== 測試三：check_local_schedule_heartbeat.py 彙整判斷（含守門員自我失敗情境）===")
        test_aggregator(tmpdir)
    print(f"\n{'=' * 40}\n總結：{'全部通過' if not FAIL else f'{len(FAIL)} 項失敗：{FAIL}'}")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    raise SystemExit(main())
