# -*- coding: utf-8 -*-
"""先.十四-一／先.十六-三 自測：三支 launcher 的登入過期／額度偵測鏈＋連續3小時無執行告警。

scripts/selftest_claude_auth_detection.py 已驗過分類器與聚合端本身；這支補的是裁示
明文要求的兩件事：
  ①「以注入假錯誤字串的自測驗證」——拿 10/3 真實事故的原文字串
    （"Failed to authenticate: OAuth session expired and could not be refreshed"）
    走一遍 marathon／hypothesis_queue／devqueue 三支各自的輸入格式，確認都分類成
    AUTH_EXPIRED；另注入額度字串確認 QUOTA_EXCEEDED。
  ②「連續 3 小時沒有任何一筆實際執行（非節流／非佇列空）即告警」——構造心跳檔，
    確認 BLOCKED_BY_RULE／QUEUE_EMPTY 這類「本來就不該做事」的輪次不會把
    last_attempt_at 推新（＝不會把停擺掩蓋成正常），3 小時後聚合端判 STALLED_3H。

全部在暫存目錄進行，不碰真實的 claude_launcher_heartbeat.json 與 data/STATUS.json。
"""
import importlib
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import claude_auth_classifier as CL  # noqa: E402

AUTH_REAL = 'Failed to authenticate: OAuth session expired and could not be refreshed'
results = []


def check(name, ok):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


# ① 注入假錯誤字串：三支 launcher 各自的輸入格式
marathon_jsonl = (
    '{"type":"system","subtype":"init","session_id":"x"}\n'
    '{"type":"assistant","message":{"content":[{"type":"text","text":"' + AUTH_REAL + '"}]}}\n'
    '{"type":"result","is_error":true,"result":"' + AUTH_REAL + '"}\n')
hq_text = ("===== Hypothesis-queue cycle start: 2026-10-03 10:30:00 =====\n" + AUTH_REAL + "\n")
dq_jsonl = '{"type":"result","is_error":true,"result":"' + AUTH_REAL + '"}\n'
for name, text in (("marathon(stream-json)", marathon_jsonl), ("hypothesis_queue(純文字log)", hq_text),
                   ("devqueue(stream-json)", dq_jsonl)):
    check(f"{name} 真實事故字串→AUTH_EXPIRED", CL.classify_text(text)["status"] == "AUTH_EXPIRED")

for text in ("Claude usage limit reached", "Your credit balance is too low", "429 Too Many Requests"):
    check(f"額度字串→QUOTA_EXCEEDED：{text[:28]}", CL.classify_text(text)["status"] == "QUOTA_EXCEEDED")
check("正常輪次輸出→OK（不誤報紅色橫幅）",
      CL.classify_text('{"type":"result","is_error":false,"result":"本輪完成，已 commit"}')["status"] == "OK")
check("空字串→OK", CL.classify_text("")["status"] == "OK")
check("壞路徑→UNKNOWN（降級不拋例外）", CL.classify_file("Q:/nope/none.jsonl")["status"] == "UNKNOWN")

# ② 心跳寫入語意：節流/佇列空不得更新 last_attempt_at
with tempfile.TemporaryDirectory() as td:
    hb = Path(td) / "claude_launcher_heartbeat.json"
    import update_claude_launcher_heartbeat as UH
    importlib.reload(UH)
    UH.PATH = hb
    UH.record("marathon", "c1", "OK", "first")
    first_attempt = json.loads(hb.read_text(encoding="utf-8"))["marathon"]["last_attempt_at"]
    for r in ("BLOCKED_BY_RULE", "QUEUE_EMPTY"):
        UH.record("marathon", "c2", r, "throttle")
    d = json.loads(hb.read_text(encoding="utf-8"))["marathon"]
    check("節流/佇列空不推新 last_attempt_at", d["last_attempt_at"] == first_attempt)
    check("節流輪次仍更新 last_checked_at", d["last_checked_at"] >= first_attempt)
    UH.record("marathon", "c3", "AUTH_EXPIRED", "oauth expired")
    d = json.loads(hb.read_text(encoding="utf-8"))["marathon"]
    # 時間戳只到秒，同一秒內連續寫入會相等，所以用「這一次確實更新了」而非「變新了」來驗：
    # AUTH_EXPIRED 不在 NO_ATTEMPT_REASONS 內，且 last_attempt_at 必等於本次的 last_checked_at。
    check("AUTH_EXPIRED 算一次實際嘗試（有想做卻做不了）",
          "AUTH_EXPIRED" not in UH.NO_ATTEMPT_REASONS and d["last_attempt_at"] == d["last_checked_at"])
    check("AUTH_EXPIRED 不更新 last_ok_at", d.get("last_ok_at") is not None and d["last_ok_at"] == first_attempt)

    # ③ 聚合端：3 小時門檻與三支 launcher 的 overall 判定
    import check_local_schedule_heartbeat as CH
    importlib.reload(CH)
    CH.CLAUDE_AUTH_PATH = hb
    now = datetime.now(timezone.utc)
    old = (now - timedelta(hours=8)).astimezone().isoformat(timespec="seconds")
    recent = (now - timedelta(minutes=10)).astimezone().isoformat(timespec="seconds")

    def write(d):
        hb.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

    write({n: {"last_reason": "OK", "last_attempt_at": recent, "last_ok_at": recent}
           for n in CH.CLAUDE_AUTH_LAUNCHERS})
    check("三支皆近期有執行→OK", CH._evaluate_claude_auth(now)["overall_status"] == "OK")
    write({n: {"last_reason": "OK", "last_attempt_at": old, "last_ok_at": old} for n in CH.CLAUDE_AUTH_LAUNCHERS})
    r = CH._evaluate_claude_auth(now)
    check("三支皆逾門檻（devqueue 3h／其餘 7h）無實際執行→STALLED_3H", r["overall_status"] == "STALLED_3H")
    check("STALLED_3H detail 含小時數", "h)" in r["detail"])
    d2 = {n: {"last_reason": "OK", "last_attempt_at": recent, "last_ok_at": recent} for n in CH.CLAUDE_AUTH_LAUNCHERS}
    d2["marathon"] = {"last_reason": "AUTH_EXPIRED", "last_attempt_at": recent, "last_detail": "oauth"}
    write(d2)
    check("任一支 AUTH_EXPIRED→整體 AUTH_EXPIRED（優先於 STALLED）",
          CH._evaluate_claude_auth(now)["overall_status"] == "AUTH_EXPIRED")
    d2["marathon"] = {"last_reason": "QUOTA_EXCEEDED", "last_attempt_at": recent}
    write(d2)
    check("任一支 QUOTA_EXCEEDED→整體 QUOTA_EXCEEDED",
          CH._evaluate_claude_auth(now)["overall_status"] == "QUOTA_EXCEEDED")
    # 10/3 真實事故重演：節流跳過照常寫 cycle log，但沒有任何一筆實際執行
    write({n: {"last_reason": "BLOCKED_BY_RULE", "last_attempt_at": old,
               "last_checked_at": recent, "last_ok_at": old} for n in CH.CLAUDE_AUTH_LAUNCHERS})
    check("10/3事故重演：持續節流但39小時無實際執行→仍告警",
          CH._evaluate_claude_auth(now)["overall_status"] == "STALLED_3H")
    # 守門員自身失敗：壞 JSON 與檔案不存在都只降級成 UNKNOWN
    hb.write_text("{壞JSON", encoding="utf-8")
    check("壞 JSON→UNKNOWN（降級不拋例外）", CH._evaluate_claude_auth(now)["overall_status"] == "UNKNOWN")
    hb.unlink()
    check("心跳檔不存在→UNKNOWN（初始狀態非錯誤）", CH._evaluate_claude_auth(now)["overall_status"] == "UNKNOWN")
    CH.CLAUDE_AUTH_PATH = Path("Q:/nonexistent/hb.json")
    check("不可讀磁碟機→UNKNOWN", CH._evaluate_claude_auth(now)["overall_status"] == "UNKNOWN")

n_fail = sum(1 for _, ok in results if not ok)
print(f"合計 {len(results)} 項，失敗 {n_fail}")
sys.exit(1 if n_fail else 0)
