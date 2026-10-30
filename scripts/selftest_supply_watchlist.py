#!/usr/bin/env python3
"""先.一三五-1dx：供給吃緊觀察清單（scripts/build_supply_watchlist.py，本機排程 AlphaSupplyWatchlist）合成自測。

零外部請求、不讀真實價格、不算報酬：FinMind 快取路徑（fc._cache_path）換到暫存目錄、抓取函式換假的，
paper_supply_v2 換成假模組（只給 quarter_table_from_frames／target_period／deadline／STMT_DS／STMT_START）。
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import time
import types
from pathlib import Path

import numpy as np
import pandas as pd

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
fails: list[str] = []
total = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global total
    total += 1
    print(("PASS " if ok else "FAIL ") + name + (f"（{detail}）" if detail and not ok else ""))
    if not ok:
        fails.append(name)


def load():
    spec = importlib.util.spec_from_file_location("bsw_selftest", ROOT / "scripts" / "build_supply_watchlist.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = load()
DS = [("fs", "FS"), ("bs", "BS"), ("cf", "CF")]
P = pd.Period("2026Q2", freq="Q")


def frame(dates):
    return pd.DataFrame({"date": pd.to_datetime(dates), "value": range(len(dates))})


with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    orig_path, orig_fetch = m.fc._cache_path, m.fc._fetch
    m.fc._cache_path = lambda ds, c, s, e: tmp / f"{ds}__{c}.parquet"
    try:
        # has_period
        good = tmp / "good.parquet"
        frame(["2026-03-31", "2026-06-30"]).to_parquet(good)
        old = tmp / "old.parquet"
        frame(["2025-12-31"]).to_parquet(old)
        empty = tmp / "empty.parquet"
        pd.DataFrame({"date": pd.to_datetime([])}).to_parquet(empty)
        broken = tmp / "broken.parquet"
        broken.write_bytes(b"not parquet")
        check("has_period 有該季 True", m.has_period(good, P))
        check("has_period 沒有該季 False", not m.has_period(old, P))
        check("has_period 空表／壞檔／不存在都 False 不拋例外",
              not m.has_period(empty, P) and not m.has_period(broken, P) and not m.has_period(tmp / "nope.parquet", P))

        # plan_fetch：缺檔 → missing；沒該季且舊 → stale；沒該季但新 → 不抓；有該季 → 不抓
        frame(["2026-06-30"]).to_parquet(tmp / "FS__A.parquet")
        for ds in ("BS", "CF"):
            frame(["2025-12-31"]).to_parquet(tmp / f"{ds}__A.parquet")
        old_ts = time.time() - (m.STMT_RETRY_DAYS + 1) * 86400
        os.utime(tmp / "BS__A.parquet", (old_ts, old_ts))
        missing, stale = m.plan_fetch(["A", "B"], DS, "2019-01-01", P, time.time())
        check("plan_fetch 缺檔全列 missing", missing == [("B", "FS"), ("B", "BS"), ("B", "CF")], str(missing))
        check("plan_fetch 只有逾 7 天未入庫的列 stale", stale == [("A", "BS")], str(stale))

        # fetch_phase（main 已不呼叫，但仍保留；測停止條件）
        def run_fetch(errs, budget=500):
            seq = iter(errs)

            def fake(ds, c, s, e, force_refresh=False):
                x = next(seq, None)
                if x:
                    raise RuntimeError(x)
            m.fc._fetch = fake
            return m.fetch_phase(["B", "C", "D", "E", "F", "G", "H", "I", "J", "K"], DS, "2019-01-01", P, budget, 0)
        st = run_fetch([], budget=4)
        check("fetch_phase 額度用完停", st["calls"] == 4 and st["stopped"] == "budget" and st["ok"] == 4, str(st))
        st = run_fetch([None, "HTTP 403 Forbidden"])
        check("fetch_phase 遇 403 立即停（不重試）", st["calls"] == 2 and st["stopped"] == "blocked", str(st))
        st = run_fetch(["HTTP 400 bad"] * 3)
        check("fetch_phase HTTP 400 只略過該檔繼續", st["fail"] == 3 and st["stopped"] is None and st["ok"] == 27, str(st))
        st = run_fetch(["timeout"] * 30)
        check("fetch_phase 連續 25 次失敗停", st["fail"] == 25 and st["stopped"] == "too_many_failures", str(st))
        m.fc._fetch = orig_fetch

        # compute：10 檔 A 產業（自成一桶）、3 檔 B 產業（<8 併「其他」）、1 檔只 2 個指標（不計分）、1 檔沒快取、1 檔壞快取
        for f in tmp.glob("*__*.parquet"):
            f.unlink()
        codes, inds = [], []
        for i in range(10):
            codes.append(f"A{i}"); inds.append("甲")
        for i in range(3):
            codes.append(f"B{i}"); inds.append("乙")
        codes += ["T2", "NC", "BR"]; inds += ["甲", "甲", "甲"]
        uni = pd.DataFrame({"code": codes, "name": codes, "industry": inds})
        vals = {c: [float(i), float(-i), np.nan if c == "T2" else 0.5 * i, float(i % 3)] for i, c in enumerate(codes)}
        vals["T2"][1] = np.nan
        for c in codes:
            if c == "NC":
                continue
            for _, ds in DS:
                p = tmp / f"{ds}__{c}.parquet"
                if c == "BR" and ds == "BS":
                    p.write_bytes(b"broken")
                else:
                    pd.DataFrame({"code": [c]}).to_parquet(p)

        def qtab(fs, bs, cf):
            c = fs["code"].iloc[0]
            return pd.DataFrame([vals[c]], index=pd.PeriodIndex([P]), columns=m.COLS)
        pv2 = types.SimpleNamespace(quarter_table_from_frames=qtab)
        df, n_cache, n_period, n_bucket = m.compute(uni, DS, "2019-01-01", P, pv2)
        r = df.set_index("code")
        check("compute 入庫計數：沒快取／壞快取不算入庫", n_period == 14 and not r.at["NC", "in"] and not r.at["BR", "in"], f"{n_period}")
        check("compute 有任何快取才算 n_cache（壞一張仍算）", n_cache == 15, f"{n_cache}")
        check("compute 指標 <3 不計分", not r.at["T2", "scored"] and r.at["T2", "n_ind"] == 2)
        check("compute 小產業併「其他」桶", set(r.loc[["B0", "B1", "B2"], "bucket"]) == {"其他"} and r.at["A0", "bucket"] == "甲")
        check("compute 桶大小只算可計分", n_bucket == {"甲": 10, "其他": 3}, str(n_bucket))
        pa = r.loc[[f"A{i}" for i in range(10)], "p1"]
        check("compute 桶內百分位落在 (0,1] 且遞增", pa.between(0, 1).all() and pa.is_monotonic_increasing and pa.iloc[-1] == 1.0)
        check("compute 不計分者沒有百分位", np.isnan(r.at["T2", "p1"]))

        # build_payload
        pay = m.build_payload(df, uni, P, pd.Timestamp("2026-08-14"), n_cache, n_period, n_bucket,
                              {"calls": 0}, "2026-10-30")
        rows = pay["rows"]
        check("build_payload 只輸出已入庫列", len(rows) == 14 and all(x["in"] for x in rows))
        t2 = next(x for x in rows if x["c"] == "T2")
        check("build_payload NaN 輸出 None（合法 JSON）", t2["v"][1] is None and t2["p"][0] is None
              and json.loads(json.dumps(pay, allow_nan=False)) is not None)
        keys = {k for x in rows for k in x}
        check("build_payload 沒有價格／分數／排名欄位", keys == {"c", "n", "i", "b", "in", "ni", "sc", "v", "p"}, str(keys))
        check("build_payload 覆蓋率與計數", pay["meta"]["n_universe"] == 16 and pay["meta"]["coverage_period"] == round(14 / 16, 4))

        # same_content 忽略 as_of／fetch
        b = json.loads(json.dumps(pay))
        b["meta"]["as_of"] = "2026-10-31"; b["meta"]["fetch"] = {"calls": 9}
        check("same_content 忽略 as_of／fetch", m.same_content(pay, b))
        b["rows"][0]["v"][0] = 99.0
        check("same_content 資料變了就不同", not m.same_content(pay, b))

        # main：setup_cache／universe／compute 換掉，paper_supply_v2 換假模組
        fake_pv2 = types.ModuleType("paper_supply_v2")
        fake_pv2.target_period = lambda today: P
        fake_pv2.deadline = lambda p: pd.Timestamp("2026-08-14")
        fake_pv2.STMT_DS, fake_pv2.STMT_START = DS, "2019-01-01"
        saved_mod = sys.modules.get("paper_supply_v2")
        sys.modules["paper_supply_v2"] = fake_pv2
        m.setup_cache = lambda d: None
        m.universe = lambda d: uni
        cur = {"df": df}
        m.compute = lambda u, dsm, s, p, pv: (cur["df"], n_cache, n_period, n_bucket)
        out = tmp / "out" / "supply_watchlist.json"
        out.parent.mkdir()
        argv = ["--cache-dir", str(tmp), "--out", str(out)]
        rc = m.main(argv)
        doc = json.loads(out.read_text(encoding="utf-8"))
        check("main 寫出合法 JSON、無 .tmp 殘留", rc == 0 and len(doc["rows"]) == 14 and not list(out.parent.glob("*.tmp")))
        mt = out.stat().st_mtime_ns
        rc = m.main(argv)
        check("main 內容相同不改寫", rc == 0 and out.stat().st_mtime_ns == mt)
        df2 = df.copy(); df2.loc[0, "I1"] = 123.0
        cur["df"] = df2
        doc0 = json.loads(out.read_text(encoding="utf-8")); doc0["meta"]["as_of"] = m.now_tw().strftime("%Y-%m-%d")
        out.write_text(json.dumps(doc0, ensure_ascii=False), encoding="utf-8")
        mt = out.stat().st_mtime_ns
        rc = m.main(argv)
        check("main 同日內容變了但沒 --force 不改寫", rc == 0 and out.stat().st_mtime_ns == mt)
        rc = m.main(argv + ["--force"])
        check("main --force 覆寫", rc == 0 and json.loads(out.read_text(encoding="utf-8"))["rows"][0]["v"][0] == 123.0)
        out.write_text("{壞", encoding="utf-8")
        rc = m.main(argv)
        check("main 既有檔損壞 → 重建", rc == 0 and len(json.loads(out.read_text(encoding="utf-8"))["rows"]) == 14)
        if saved_mod is not None:
            sys.modules["paper_supply_v2"] = saved_mod
        else:
            sys.modules.pop("paper_supply_v2", None)
    finally:
        m.fc._cache_path, m.fc._fetch = orig_path, orig_fetch

print(f"\n{'全過' if not fails else '失敗 ' + str(len(fails)) + ' 項'}（共 {total} 項）")
sys.exit(1 if fails else 0)
