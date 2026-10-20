# -*- coding: utf-8 -*-
"""先.一二二-11（2026-10-21）：claude_usage_gate 誤判修正自測（只用假資料＋本機既有串流檔重播，不改狀態檔）。
① 輸出只是「提到」用量上限錯誤碼（工具讀到的檔案內容／assistant 文字）→ 不觸發
② 正常狀態（status=allowed，且 overageStatus=rejected）帶每週 resetsAt → 不觸發
③ 真的 429（rate_limit_event status=rejected＋result is_error）→ 觸發，重置時間取該事件的 resetsAt
④ 只有 result 錯誤、沒有 rejected 事件 → 觸發，預設 6 小時
⑤ 重播 10/20 18:31 誤判那輪（若檔案還在）→ 不觸發；重播 10/19 10:01 真 429 那輪 → 觸發
用法：python scripts/selftest_claude_usage_gate.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import claude_usage_gate as G  # noqa: E402

NOW = 1792500000.0
CODE = "usage_limit" + "_reached"
WEEK = int(NOW) + 5 * 86400
HOUR = int(NOW) + 3600


def j(*evs):
    return "\n".join(json.dumps(e) for e in evs)


def rl(status, reset):
    return {"type": "rate_limit_event", "rate_limit_info": {
        "status": status, "resetsAt": reset, "rateLimitType": "five_hour", "overageStatus": "rejected",
        "unifiedWindows": {"five_hour": {"resetsAt": HOUR}, "seven_day": {"resetsAt": WEEK}}}}


mention = j({"type": "user", "message": {"content": [{"type": "tool_result", "content": f'檔案內容：遇到 {CODE} 就讀 "resetsAt": {WEEK}'}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": f"parse_limit 會找 {CODE}"}]}},
            {"type": "result", "subtype": "success", "is_error": False, "result": f"改好了 {CODE}"})
normal = j(rl("allowed", HOUR), rl("allowed", HOUR), {"type": "result", "subtype": "success", "is_error": False})
real = j(rl("rejected", WEEK),
         {"type": "assistant", "error": "rate_limit", "api_error": CODE, "message": {"content": [{"type": "text", "text": "You've hit your weekly limit"}]}},
         {"type": "result", "subtype": "success", "is_error": True, "api_error_status": 429, "api_error": CODE})
only_result = j({"type": "result", "is_error": True, "api_error": CODE})

res = [("①只提到錯誤碼（工具輸出／文字）→ 不觸發", G.parse_limit(mention, NOW) is None),
       ("②正常 allowed 帶每週 resetsAt（overageStatus=rejected）→ 不觸發", G.parse_limit(normal, NOW) is None),
       ("③真 429 → 觸發並取該事件 resetsAt", G.parse_limit(real, NOW) == (float(WEEK), "resetsAt")),
       ("④只有 result 錯誤 → 觸發、預設 6 小時", G.parse_limit(only_result, NOW) == (NOW + G.DEFAULT_WAIT_SEC, "預設 6 小時")),
       ("混合：真 429 前後夾雜提到錯誤碼的工具輸出 → 只取 rejected 事件的時間", G.parse_limit(mention + "\n" + normal + "\n" + real, NOW) == (float(WEEK), "resetsAt"))]

cyc = ROOT / "research" / "data" / "dev_cycles"
false_run, real_run = cyc / "20261020-183102.jsonl", cyc / "20261019-100102.jsonl"
if false_run.exists():
    t = false_run.read_text(encoding="utf-8", errors="replace")
    res.append(("⑤重播 10/20 18:31 誤判那輪 → 不觸發", G.parse_limit(t, 1792494723.0) is None))
if real_run.exists():
    t = real_run.read_text(encoding="utf-8", errors="replace")
    got = G.parse_limit(t, 1792375000.0)
    res.append(("⑤重播 10/19 10:01 真 429 那輪 → 觸發、重置 10/20 04:00", got is not None and G._fmt(got[0]) == "10/20 04:00"))

for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
bad = [n for n, ok in res if not ok]
print(f"{len(res) - len(bad)}/{len(res)} PASS")
sys.exit(1 if bad else 0)
