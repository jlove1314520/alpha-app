# -*- coding: utf-8 -*-
"""先.六十四-7 自測：DevQueue 趕工迴圈（scripts/dev_queue_crunch.py）。

全程沙盒：佇列、狀態、鎖、log、PROGRESS、心跳都改指到暫存目錄；claude 換成假執行器、推播換成假函式、
排程切換換成假 PowerShell。不連網、不呼叫 claude、不改工作排程器、不碰真佇列。
裁示指定三個情境：①3 個假項目連跑 ②中斷後重啟續做 ③同一項失敗兩次跳過；另測額度用盡停輪不算失敗、
gate 10／20 分鐘規則、趕工結束判定、排程切換參數、提示詞趕工版只做一項。
"""
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dev_queue_runner as R  # noqa: E402
import dev_queue_crunch as C  # noqa: E402

results = []


def check(name, ok):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


tmp = Path(tempfile.mkdtemp())
saved = {k: getattr(R, k) for k in ("QUEUE", "STATE", "PROMPT_OUT", "DIRTY_SEEN")}
saved_c = {k: getattr(C, k) for k in ("LOCK", "LOG", "CYCLES_DIR", "HEARTBEAT", "PROGRESS", "CRUNCH_STATE")}
try:
    R.QUEUE, R.STATE, R.PROMPT_OUT, R.DIRTY_SEEN = tmp / "Q.md", tmp / "state.json", tmp / "PROMPT.txt", tmp / "dirty.json"
    C.LOCK, C.LOG, C.CYCLES_DIR = tmp / ".devqueue.lock", tmp / "cycle.log", tmp / "cycles"
    C.HEARTBEAT, C.PROGRESS, C.CRUNCH_STATE = tmp / "HB.jsonl", tmp / "PROGRESS.md", tmp / "crunch.json"
    C.PROGRESS.write_text("# PROGRESS\n\n## 舊段落\n", encoding="utf-8")
    C.HEARTBEAT.write_text("", encoding="utf-8")

    def queue(items):
        R.QUEUE.write_text("# 測試佇列\n\n<!-- ORDER-BEGIN -->\n<!-- ORDER-END -->\n\n" +"\n".join(f"- [ ] **常備.開發-{n} 假項目{n}**〔做法：改一個字〕" for n in items) + "\n", encoding="utf-8")
        R.STATE.write_text("{}", encoding="utf-8")

    def lock(cycle, age_min=0.0):
        C.LOCK.write_text(f"999|{time.time() - age_min * 60}|{cycle}", encoding="utf-8")

    def mark_done(key):
        lines = R._lines()
        for i, ln in enumerate(lines):
            if ln.startswith("- [ ]") and R.item_key(ln) == key:
                lines[i] = ln.replace("- [ ]", "- [x]", 1) + "〔假完成〕"
        R.QUEUE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    pushes, calls = [], []

    def notify(t, b):
        pushes.append(b)

    def make_exec(fail_keys=(), die_after=None, quota_on=None):
        def ex(prompt_path, jsonl, on_alive):
            key = R._load_state()["_current"]
            calls.append(key)
            on_alive()
            jsonl.write_text("{}", encoding="utf-8")
            if die_after is not None and len(calls) > die_after:
                raise SystemExit("模擬 wrapper 中途死掉（重開機）")
            if quota_on and key.startswith(quota_on):
                return 1
            if any(key.startswith(f) for f in fail_keys):
                return 1
            mark_done(key)
            return 0
        return ex

    ok_cls = lambda _p: {"status": "OK"}  # noqa: E731
    no_col = lambda: 0  # noqa: E731

    # 提示詞：趕工版只做一項
    queue([2])
    import os
    os.environ["ALPHA_DEVQUEUE_CRUNCH"] = "1"
    R.build_prompt()
    p = R.PROMPT_OUT.read_text(encoding="utf-8")
    check("趕工版提示詞：只做這一項、不自己接下一項、PROGRESS 由迴圈寫", "這一次只做上面這一項" in p and "不要自己接著做下一項" in p and "不用**寫 PROGRESS.md" in p)
    os.environ.pop("ALPHA_DEVQUEUE_CRUNCH")
    R.build_prompt()
    p = R.PROMPT_OUT.read_text(encoding="utf-8")
    check("非趕工提示詞維持原本「一輪做多項」", "一輪之內連續做多項" in p and "這一次只做上面這一項" not in p)

    # ① 3 個假項目連跑
    queue([2, 3, 4])
    lock("CYC1")
    calls.clear(); pushes.clear()
    code, s = C.run_round("CYC1", executor=make_exec(), classifier=ok_cls, notify=notify, collision=no_col)
    check(f"①3 項連跑：依序派 2→3→4（{[c[:9] for c in calls]}）", [c.split()[0] for c in calls] == ["常備.開發-2", "常備.開發-3", "常備.開發-4"])
    check("①3 項全部 [x]、收工原因＝佇列清空、exit 0", code == C.EXIT_DONE and all(i["result"] == "done" for i in s["items"]) and len(s["items"]) == 3 and "沒有" in s["stop"])
    check("①每完成一項推播一則（含項目名）", len(pushes) == 3 and all("常備.開發-" in x for x in pushes))
    hb = [json.loads(x) for x in C.HEARTBEAT.read_text(encoding="utf-8").splitlines() if x.strip()]
    check("①每完成一項心跳一行（track=devqueue）", [h["round"] for h in hb] == ["常備.開發-2", "常備.開發-3", "常備.開發-4"] and all(h["track"] == "devqueue" for h in hb))
    pg = C.PROGRESS.read_text(encoding="utf-8")
    check("①收工寫 PROGRESS 一段（完成 3 項、剩餘 0 項），寫在最上面", "完成 3 項" in pg and "剩餘 `- [ ]`**：0 項" in pg and pg.index("先.六十四") < pg.index("舊段落"))
    check("①趕工結束判定：常備.開發 - [ ]＝0 → crunch_active False", not C.crunch_active())
    check("①鎖心跳在跑的過程中有刷新", abs(float(C.LOCK.read_text().split("|")[1]) - time.time()) < 60)

    # ② 中斷重啟續做：第 1 項做完後 wrapper 死掉（鎖留著），20 分鐘內不搶、超過 20 分鐘清鎖，從第一個未完成項續做
    queue([5, 6, 7])
    lock("CYC2")
    calls.clear()
    try:
        C.run_round("CYC2", executor=make_exec(die_after=1), classifier=ok_cls, notify=notify, collision=no_col)
        died = False
    except SystemExit:
        died = True
    check("②模擬中斷：第 2 項途中 wrapper 死掉、鎖檔留著", died and C.LOCK.exists())
    c1, m1 = C.gate(now=time.time() + 5 * 60)
    c2, m2 = C.gate(now=time.time() + 15 * 60)
    check(f"②心跳 5 分鐘前 → 略過（{c1}）；15 分鐘 → 保守略過（{c2}）", c1 == 1 and c2 == 1 and C.LOCK.exists())
    c3, m3 = C.gate(now=time.time() + 21 * 60)
    check(f"②心跳超過 20 分鐘 → 清鎖、可開新一輪（{m3[:20]}）", c3 == 0 and not C.LOCK.exists())
    lock("CYC3")
    calls.clear()
    code, s = C.run_round("CYC3", executor=make_exec(), classifier=ok_cls, notify=notify, collision=no_col)
    check(f"②重啟後從第一個未完成項續做：6→7（{[c.split()[0] for c in calls]}）", [c.split()[0] for c in calls] == ["常備.開發-6", "常備.開發-7"])
    check("②全部完成", all(ln.startswith("- [x]") for ln in R._lines() if "常備.開發-" in ln))

    # ③ 同一項失敗兩次 → 標 [!]、換下一項繼續
    queue([8, 9])
    lock("CYC4")
    calls.clear()
    code, s = C.run_round("CYC4", executor=make_exec(fail_keys=("常備.開發-8",)), classifier=ok_cls, notify=notify, collision=no_col)
    seq = [c.split()[0] for c in calls]
    check(f"③常備.開發-8 連敗兩次後跳過、接著做 9（{seq}）", seq == ["常備.開發-8", "常備.開發-8", "常備.開發-9"])
    l8 = next(ln for ln in R._lines() if "常備.開發-8" in ln)
    check("③常備.開發-8 被標 [!] 並寫原因；9 完成", l8.startswith("- [!]") and "連續 2 次" in l8 and next(ln for ln in R._lines() if "常備.開發-9" in ln).startswith("- [x]"))
    check("③結算紀錄：fail → fail_blocked → done", [i["result"] for i in s["items"]] == ["fail", "fail_blocked", "done"])

    # 額度用盡：停輪、不算該項失敗、寫預估恢復說明
    queue([10, 11])
    lock("CYC5")
    calls.clear()
    code, s = C.run_round("CYC5", executor=make_exec(quota_on="常備.開發-10"), classifier=lambda _p: {"status": "QUOTA_EXCEEDED", "matched": "usage limit"},
                          notify=notify, collision=no_col)
    check("額度用盡 → 停輪 exit 11、不累計失敗、收工原因寫恢復說明", code == C.EXIT_QUOTA and R._load_state().get("常備.開發-10 假項目10") is None and "額度用盡" in s["stop"]
          and next(ln for ln in R._lines() if "常備.開發-10" in ln).startswith("- [ ]"))
    jb = tmp / "budget.jsonl"
    jb.write_text('{"type":"result","error":"Exceeded max budget of $12"}', encoding="utf-8")
    jq = tmp / "quota.jsonl"
    jq.write_text('{"type":"result","error":"Claude usage limit reached, resets 3pm"}', encoding="utf-8")
    check("單項預算用完（max budget）→ ITEM_BUDGET（算該項失敗、不停輪）；帳號額度 → QUOTA_EXCEEDED",
          C.classify(jb)["status"] == "ITEM_BUDGET" and C.classify(jq)["status"] == "QUOTA_EXCEEDED" and "3pm" in C._quota_reset_hint(jq))
    # 撞車讓路
    lock("CYC6")
    code, s = C.run_round("CYC6", executor=make_exec(), classifier=ok_cls, notify=notify, collision=lambda: 1)
    check("其他軌道持鎖 → 讓路收工 exit 12、不派工", code == C.EXIT_YIELD and not s["items"])
    # 排程切換參數（假 PowerShell）
    got = []
    C.set_schedule("crunch", runner=lambda ps: (got.append(ps), "OK")[1])
    C.set_schedule("normal", runner=lambda ps: (got.append(ps), "OK")[1])
    check("排程切換：趕工每 30 分鐘＋上限 12 小時；恢復每 15 分鐘＋上限 1 小時 10 分", "PT30M" in got[0] and "PT12H" in got[0] and "PT15M" in got[1] and "PT1H10M" in got[1])
    # 守門員自身失敗只降級：crunch_active 讀檔失敗 → False、不拋例外
    R.QUEUE = tmp / "不存在.md"
    check("crunch_active 讀不到佇列 → 降級為 False、不拋例外", C.crunch_active() is False)
finally:
    for k, v in saved.items():
        setattr(R, k, v)
    for k, v in saved_c.items():
        setattr(C, k, v)
    shutil.rmtree(tmp, ignore_errors=True)

n_fail = sum(1 for _, ok in results if not ok)
print(f"合計 {len(results)} 項，失敗 {n_fail}")
sys.exit(1 if n_fail else 0)
