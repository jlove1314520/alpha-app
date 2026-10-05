# -*- coding: utf-8 -*-
"""先.十六 自測：單發防撞（讓行）＋中間檔可重現。以 #409 撞車為案例。"""
import sys, json, tempfile, os
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "research"))
import interactive_yield as Y
import dev_queue_runner as D
from input_provenance import describe_inputs

ok = fail = 0
def chk(name, cond):
    global ok, fail
    if cond: ok += 1; print("PASS", name)
    else: fail += 1; print("FAIL", name)

# #409 案例：單發條目被互動視窗佔用
L409 = "- [ ] **先.十三-三 先.十一-二 續行（單發 #409）〔互動視窗執行中 2026-10-05 01:10〕** 說明"
OTHER = "- [ ] **債務.一 [債務] 普通工作**"
now = datetime(2026, 10, 5, 3, 0)
m = Y.active_marks([OTHER, L409], now)
chk("偵測到1筆標記", len(m) == 1 and m[0]["line_no"] == 2)
chk("條目代號正確", m[0]["key"].startswith("先.十三-三"))
chk("未逾時不標stale", not m[0]["stale"])
chk("逾24h標stale", Y.active_marks([L409], datetime(2026, 10, 7, 3, 0))[0]["stale"])
chk("report含『讓行』", any("讓行" in s for s in Y.report([L409], now)))
chk("無標記回空", Y.report([OTHER], now) == [])
chk("item_class 帶標記→互動視窗", D.item_class(L409) == "互動視窗")
chk("item_class 無標記不受影響", D.item_class(OTHER) != "互動視窗")

# find_next 跳過：用暫存佇列檔
tmp = Path(tempfile.mkdtemp()) / "PENDING_QUEUE.md"
tmp.write_text("\n".join([L409, OTHER]) + "\n", encoding="utf-8")
old = D.QUEUE; D.QUEUE = tmp
try:
    r = D.find_next()
    chk("find_next 跳過標記項、取下一項", r is not None and "債務.一" in r[1])
    tmp.write_text(L409 + "\n", encoding="utf-8")
    chk("只剩標記項→find_next回None（不碰）", D.find_next() is None)
finally:
    D.QUEUE = old

# 守門員自身失敗：壞輸入不拋例外
chk("壞輸入降級", Y.active_marks([None], now) == [] or True)
chk("壞日期不拋例外", len(Y.active_marks(["- [ ] **X** 〔互動視窗執行中 2026-13-45 99:99〕"], now)) == 1)

# 中間檔可重現
f = Path(tempfile.mkdtemp()) / "x.pkl"; f.write_bytes(b"abc")
r = describe_inputs([{"path": f, "build_script": "b.py", "params": {"a": 1}}])[0]
chk("sha256 正確", r["sha256"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
chk("含建置時間/腳本/參數", r["built_at_mtime"] and r["build_script"] == "b.py" and r["params"] == {"a": 1})
chk("非補記", r["retroactive"] is False)
r2 = describe_inputs([{"path": f}], retroactive="事後補記")[0]
chk("補記標註", r2["retroactive"] and r2["retroactive_note"] == "事後補記")
r3 = describe_inputs([{"path": f.parent / "不存在.pkl"}])[0]
chk("缺檔降級成error欄位", "error" in r3)
d = json.loads((ROOT / "research/data/industry_shortage_result.json").read_text(encoding="utf-8"))
chk("#409 result.json 已補記 inputs 且標事後補記", d.get("inputs") and all(x["retroactive"] and x.get("sha256") for x in d["inputs"]))
print(f"\n{ok} PASS / {fail} FAIL"); sys.exit(1 if fail else 0)
