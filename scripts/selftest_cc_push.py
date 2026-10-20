# -*- coding: utf-8 -*-
"""先.一二二-14 自測：cc_push 用暫存檔＋假推播（不送真推播、不碰真狀態檔）。
① 第一次執行只記位置不推  ② 新心跳＋條目已 - [x] → 推一則 cc_done，標題含編號  ③ 分批心跳（條目仍 - [ ]）→ 不推
④ 同一條第二次心跳 → 不再推  ⑤ 自走補入條目 → 不推  ⑥ 超過 3 小時沒進度 → cc_stuck，6 小時內同原因不重推
⑦ 用量閘門擋住 → cc_stuck  ⑧ 22:00 後推一次 cc_daily、數字正確，同日不重推；22:00 前不推
⑨ 推播送不到（NO_SUBSCRIPTION）→ 只警告、不拋例外  ⑩ 心跳檔壞行／半行 → 跳過不崩
用法：python scripts/selftest_cc_push.py
"""
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import cc_push as C  # noqa: E402

tmp = Path(tempfile.mkdtemp())
C.STATE, C.HB, C.PQ, C.AWAIT, C.USAGE, C.DQ_LOG = (tmp / n for n in ("st.json", "hb.jsonl", "pq.md", "aw.md", "u.json", "dq.log"))
sent = []
ok = lambda t, b, k: (sent.append((k, t, b)), {"ok": 1})[1]  # noqa: E731
now = datetime.fromisoformat("2026-10-21T15:00:00+08:00")


def hb(item, ts="2026-10-21T14:50:00+08:00", summary="摘要"):
    with C.HB.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": ts, "item": item, "summary": summary}, ensure_ascii=False) + "\n")


C.PQ.write_text("- [x] **先.九-1 修好某個東西（DevQueue 可執行）**〔完成〕\n- [ ] **先.九-2 V1 分批補資料**（分批）\n"
                "- [x] **先.九-3 [自走補入，來源] 補件**\n- [ ] **先.九-4 另一件**\n", encoding="utf-8")
C.AWAIT.write_text("## 等待中（目前：1件）\n\n| 項目 | 完成時間 | 等待審閱內容 | 等待時長 |\n|---|---|---|---|\n| X | a | b | c |\n\n## 等前置條件\n", encoding="utf-8")
hb("先.九-0 舊的")
st = {}
res = [("①第一次只記位置不推", C.scan(st, ok) == 0 and not sent and st["hb_offset"] > 0)]
hb("先.九-1")
hb("先.九-2", summary="第 3 批")
hb("先.九-3")
n = C.scan(st, ok)
res.append(("②已打勾 → 推 cc_done、含編號與短標題", n == 1 and sent[0][0] == "cc_done" and sent[0][1].startswith("✅ 做完：先.九-1 修好某個東西")))
res.append(("③分批心跳（仍 - [ ]）不推、⑤自走補入不推", len(sent) == 1))
hb("先.九-1", summary="又一次")
res.append(("④同一條第二次不再推", C.scan(st, ok) == 0 and len(sent) == 1))
with C.HB.open("a", encoding="utf-8") as f:
    f.write("壞行不是json\n{\"ts\": \"2026-10")  # 半行
res.append(("⑩壞行／半行跳過不崩", C.scan(st, ok) == 0))
C.HB.write_bytes(C.HB.read_bytes() + b'-21T14:59:00+08:00", "item": "x"}\n')
C.scan(st, ok)

late = datetime.fromisoformat("2026-10-21T18:30:00+08:00")
s0 = len(sent)
C.stuck(st, late, ok)
res.append(("⑥超過 3 小時沒進度 → cc_stuck", len(sent) == s0 + 1 and sent[-1][0] == "cc_stuck" and "3 小時" in sent[-1][2]))
C.stuck(st, datetime.fromisoformat("2026-10-21T20:00:00+08:00"), ok)
res.append(("⑥同原因 6 小時內不重推", len(sent) == s0 + 1))
C.USAGE.write_text(json.dumps({"limited_until": late.timestamp() + 3600}), encoding="utf-8")
C.stuck(st, late, ok)
res.append(("⑦用量閘門擋住 → cc_stuck", len(sent) == s0 + 2 and "用量上限" in sent[-1][2]))

s1 = len(sent)
C.daily(st, datetime.fromisoformat("2026-10-21T21:59:00+08:00"), ok)
res.append(("⑧22:00 前不推", len(sent) == s1))
C.daily(st, datetime.fromisoformat("2026-10-21T22:01:00+08:00"), ok)
res.append(("⑧22:00 後推 cc_daily：做完 2（九-1、九-3）、還剩 2、等決定 1", len(sent) == s1 + 1 and sent[-1][0] == "cc_daily"
            and sent[-1][2] == "今天做完 2 件、還剩 2 件、等你決定 1 件"))
C.daily(st, datetime.fromisoformat("2026-10-21T22:31:00+08:00"), ok)
res.append(("⑧同日不重推", len(sent) == s1 + 1))

C.PQ.write_text(C.PQ.read_text(encoding="utf-8").replace("- [ ] **先.九-4", "- [x] **先.九-4"), encoding="utf-8")
hb("先.九-4")
try:
    C.scan(st, lambda t, b, k: {"ok": 0, "errors": ["NO_SUBSCRIPTION:沒有任何裝置訂閱推播"]})
    res.append(("⑨送不到只警告、不拋例外", True))
except Exception as e:  # noqa: BLE001
    res.append((f"⑨送不到只警告、不拋例外（拋了 {e}）", False))

for nm, good in res:
    print(("PASS " if good else "FAIL ") + nm)
bad = [nm for nm, good in res if not good]
print(f"{len(res) - len(bad)}/{len(res)} PASS")
sys.exit(1 if bad else 0)
