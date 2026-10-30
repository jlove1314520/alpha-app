# -*- coding: utf-8 -*-
"""先.一三四-1（2026-10-23，收件匣 022）自測：「CC 停住」推播不再誤報。不讀真 repo 狀態、不發推播（換成假的來源與送出）。

1. 只有 commit、沒有心跳（心跳 5 小時前、人工 commit 10 分鐘前）→ 不推；
2. 三者都超過 3 小時、佇列有可執行項目 → 推「⚠️ CC 停住」，內文附最後一個進度（commit 標題前 30 字）；
3. 三者都超過 3 小時、DevQueue 最後一輪 QUEUE_EMPTY → 推「⏸ 佇列都在等審／等條件」（不同訊息）；
4. 同一原因 6 小時內不重推；
5.（收件匣 032）2026-10-30 07:10～09:38 DevQueue 的「補件／合成自測／收工」commit 都算人工進度（不被當成機器提交排除）。
跑法：python scripts/selftest_cc_push_stuck.py
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import cc_push as C  # noqa: E402

now = datetime(2026, 10, 23, 17, 0, tzinfo=C.TW)
fails = []


def check(name, ok, detail=""):
    print(f"{'OK  ' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        fails.append(name)


def setup(hb_h, git_h, done_h, executable):
    C._hb_last = lambda n: (now - timedelta(hours=hb_h), "心跳：舊條目") if hb_h is not None else None
    C._git_last_manual = lambda n: (now - timedelta(hours=git_h), "commit：收件匣021：V1 修訂 R3（股利 FinMind＋官方") if git_h is not None else None
    C._inbox_last_done = lambda n: (now - timedelta(hours=done_h), "收件匣：021_20261023") if done_h is not None else None
    C._queue_executable = lambda: executable
    C.USAGE = Path("__no_usage__.json")
    C.DQ_LOG = Path("__no_log__.log")


sent = []
send = lambda t, b, k: sent.append((t, b, k)) or {"ok": 1}  # noqa: E731

setup(5, 10 / 60, 2, True)
st = {}
C.stuck(st, now, send=send)
check("1 只有 commit 沒心跳 → 不推", not sent, str(sent))

setup(5, 3.5, 4, True)  # 最晚的是 commit（3.5 小時前）→ 內文要帶 commit 標題
st, sent = {}, []
C.stuck(st, now, send=send)
ok = len(sent) == 1 and sent[0][0].startswith("⚠️ CC 停住") and "收件匣021：V1 修訂 R3" in sent[0][1]
check("2 三者都 >3 小時＋有可執行 → 推停住、附最後進度", ok, str(sent)[:200])

C.stuck(st, now + timedelta(hours=2), send=send)
check("4 同一原因 6 小時內不重推", len(sent) == 1, str(len(sent)))

setup(5, 4, 3.5, False)
st, sent = {}, []
C.stuck(st, now, send=send)
ok = len(sent) == 1 and sent[0][0].startswith("⏸ 佇列都在等審") and "停住" not in sent[0][0]
check("3 QUEUE_EMPTY → 推不同訊息「⏸ 佇列都在等審／等條件」", ok, str(sent)[:200])

# 5. 收件匣 032：10/30 誤報當時的 commit 標題（實際來源是 autostash 推播，見 local_git_commit；這裡守住「進度」不被誤排除）
for subj in ("DevQueue 候選補件（先.一三五-1cb～1ce）：台股報價全失敗不推空檔、ROE 近四季跨缺口湊數修",
             "先.一三五-1cn 試驗索引合成自測＋帳本讀不到／0 列時不覆寫既有輸出",
             "先.一三五-1co 新聞內文題材句萃取合成自測＋輸入讀不到時不拋未處理例外",
             "DevQueue 20261030-090102 收工：PROGRESS 紀錄＋補件 先.一三五-1ct～1cy"):
    check("5 算人工進度：" + subj[:24], not C.MACHINE_COMMIT.search(subj))
for subj in ("盤中報價：本機備援補抓（雲端 20 分鐘未更新，先.八十二-4）", "DevQueue cycle log 自動更新（cycle_id=20261030-090102）"):
    check("5 仍算機器提交：" + subj[:20], bool(C.MACHINE_COMMIT.search(subj)))

print(f"\n結果：{'全部通過' if not fails else '失敗 ' + str(fails)}")
sys.exit(1 if fails else 0)
