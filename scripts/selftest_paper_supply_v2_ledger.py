#!/usr/bin/env python3
"""先.一三五-1eg：紙.二（research/paper_supply_v2.py，本機排程 AlphaPaperSupplyV2）帳本讀寫合成自測。

只測 append-only 帳本與狀態檔的讀寫（load_log／append_events／_js／_load_state／_save_state），
全部用暫存檔：零外部請求、不讀真實價格、不碰真帳本、不算任何報酬。
用法：python scripts/selftest_paper_supply_v2_ledger.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
fails: list[str] = []
total = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global total
    total += 1
    print(("PASS " if ok else "FAIL ") + name + (f"（{detail}）" if detail and not ok else ""))
    if not ok:
        fails.append(name)


import paper_supply_v2 as P  # noqa: E402

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    log = td / "sub" / "log.jsonl"

    # load_log：檔案不存在
    ev, bad = P.load_log(log)
    check("load_log 檔案不存在 → 空、0 壞行", ev == [] and bad == 0)

    # append_events：第一次寫、批內重複只寫一次、自動建目錄
    keys: set = set()
    n = P.append_events(log, [{"key": "a", "type": "signal"}, {"key": "a", "type": "signal"},
                              {"key": "b", "type": "fill", "px": np.float64(1.5), "q": np.int64(3),
                               "d": pd.Timestamp("2026-10-30"), "p": pd.Period("2026Q3")}], keys)
    ev, bad = P.load_log(log)
    check("append_events 批內重複只寫一次", n == 2 and [e["key"] for e in ev] == ["a", "b"], f"n={n}")
    check("append_events 更新 keys", keys == {"a", "b"}, str(keys))
    check("_js numpy／Timestamp／Period 轉 JSON",
          ev[1]["px"] == 1.5 and ev[1]["q"] == 3 and ev[1]["d"] == "2026-10-30" and ev[1]["p"] == "2026Q3", str(ev[1]))

    # 已在 keys 的不重寫；全重複時不動檔案
    before = log.read_bytes()
    n = P.append_events(log, [{"key": "a"}, {"key": "b"}], keys)
    check("全重複 → 回 0、檔案不動", n == 0 and log.read_bytes() == before)

    # 上一行沒換行（例如被中斷寫一半）→ 先補換行，新事件不黏在壞行後面
    with open(log, "ab") as f:
        f.write(b'{"key": "broken"')
    n = P.append_events(log, [{"key": "c"}], keys)
    ev, bad = P.load_log(log)
    check("尾端無換行 → 補換行、新事件可讀", n == 1 and ev[-1]["key"] == "c" and bad == 1, f"bad={bad} ev={ev}")
    check("壞行只計數不改寫", b'{"key": "broken"\n' in log.read_bytes())

    # 空行與非 UTF-8 也只計數
    with open(log, "ab") as f:
        f.write(b"\n\n\xff\xfe\n")
    ev, bad = P.load_log(log)
    check("空行略過、非 UTF-8 計壞行", len(ev) == 3 and bad == 2, f"len={len(ev)} bad={bad}")

    # 不可序列化的物件 → 拋例外前不得寫入半行
    before = log.read_bytes()
    try:
        P.append_events(log, [{"key": "d", "x": object()}], keys)
        raised = False
    except TypeError:
        raised = True
    check("不可序列化 → TypeError 且檔案不動、keys 不增", raised and log.read_bytes() == before and "d" not in keys)

    # 狀態檔：壞檔／不存在 → {}；寫不進去不拋例外
    st = td / "state.json"
    check("_load_state 不存在 → {}", P._load_state(st) == {})
    st.write_text("{壞", encoding="utf-8")
    check("_load_state 壞 JSON → {}", P._load_state(st) == {})
    P._save_state(st, {"x": 1})
    check("_save_state／_load_state 來回", P._load_state(st) == {"x": 1})
    try:
        P._save_state(td / "不存在的目錄" / "s.json", {"x": 1})
        ok = True
    except Exception:  # noqa: BLE001
        ok = False
    check("_save_state 寫不進去不拋例外", ok)

print(f"\n{total - len(fails)}/{total} 通過")
sys.exit(1 if fails else 0)
