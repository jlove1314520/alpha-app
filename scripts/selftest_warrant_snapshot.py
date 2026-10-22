# -*- coding: utf-8 -*-
"""先.九十四-5a 自測：research/warrant_snapshot.py 用合成回應驗解析、寫檔前驗證、封鎖處理（不發任何網路請求）。

用法：python scripts/selftest_warrant_snapshot.py   （全過 exit 0）
"""
from __future__ import annotations

import gzip
import json
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import warrant_snapshot as W  # noqa: E402

FAIL = []


def ok(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAIL.append(msg)


def basic_row(code, half_width=True, remark=""):
    p = ("(", ")") if half_width else ("（", "）")
    return {
        "出表日期": "1151013", "權證代號": code, "權證簡稱": "友達台新6A購01", "權證類型": "認購", "類別": "一般型",
        "履約開始日": "1151005", "最後交易日": "1160930", "履約截止日": "1161004",
        f"發行單位數量{p[0]}仟單位{p[1]}": "5000", f"結算方式{p[0]}詳附註編號說明{p[1]}": "5", "標的證券/指數": "友達",
        f"最新標的履約配發數量{p[0]}每仟單位權證{p[1]}": "65.00",
        f"原始履約價格{p[0]}元{p[1]}/履約指數": "53.0000", f"最新履約價格{p[0]}元{p[1]}/履約指數": "52.5000",
        "備註": remark,
    }


def table(title, fields, data, date=None):
    js = {"stat": "OK", "tables": [{"title": None, "fields": None, "data": None},
                                   {"title": title, "fields": fields, "data": data}]}
    if date:
        js["date"] = date
    return js


TWSE_F = ["暫停交易", "證券代號", "證券名稱", "成交股數", "成交筆數", "成交金額", "開盤價", "最高價", "最低價", "收盤價",
          "漲跌(+/-)", "漲跌價差", "最後揭示買價", "最後揭示買量", "最後揭示賣價", "最後揭示賣量", "本益比",
          "標的代號", "標的名稱", "標的收盤價/指數"]
TPEX_F = ["代號", "名稱", "收盤 ", "漲跌", "開盤 ", "最高 ", "最低", "成交股數  ", " 成交金額(元)", " 成交筆數 ",
          "最後買價", "最後買量<br>(張數)", "最後賣價", "最後賣量<br>(張數)", "發行股數 ", "次日漲停價 ", "次日跌停價"]


def raw_fixture(date="2026-10-14", twse_title_date="115年10月14日", tpex_date="20261014"):
    tw_row = ["", "030001", "友達台新6A購01", "32,000", "9", "21,740", "0.66", "0.69", "0.66", "0.68",
              "<p style= color:red>+</p>", "0.04", "0.71", "25", "0.72", "25", "36.25", "2409", "友達", "36.25"]
    tw_nontrade = ["", "030002", "X", "0", "0", "0", "--", "--", "--", "--", "", "", "0.10", "25", "0.12", "25",
                   "", "2409", "友達", "36.25"]
    return {
        "twse_basic": [basic_row("030001", remark="1.美式價外認購權證"), basic_row("030002")],
        "tpex_basic": [basic_row("700019", half_width=False, remark="1.歐式價外認購權證\r\n◎2026/09/01標的證券除息，調整後履約價格166.48元")],
        "tpex_issue": [{"Date": "1151013", "Code": "700019", "UnderlyingStockCode": "3707", "Type": "認購",
                        "American/European": "歐式", "Reset": "N", "ListedDate": "20251105", "ExpiryDate": "20261231",
                        "LatestExercisePrice": "166.48", "Latest ExerciseRatio": "0.013", "Accum.CanceledWarrant": "2750"}],
        "twse_call": table(f"{twse_title_date} 每日收盤行情(認購權證(不含牛證))", TWSE_F, [tw_row, tw_nontrade]),
        "twse_put": table(f"{twse_title_date} 每日收盤行情(認售權證(不含熊證))", TWSE_F, [tw_row]),
        "tpex_ww": table("上櫃股票每日收盤行情(不含定價)", TPEX_F,
                         [["700019", "宏捷科統一5C購01", "----", "---", "----", "----", "----", "0", "0", "0",
                           "0.50", "10", "0.55", "10", "5,000,000", "0.9", "0.01"]], date=tpex_date),
        "tpex_ew": table("上櫃股票每日收盤行情(不含定價)", TPEX_F,
                         [["3707", "宏捷科", "150.50", "+1", "149", "151", "148", "1,000", "1", "1", "150", "1",
                           "151", "1", "1", "1", "1"], ["9999", "無關", "10", "", "", "", "", "", "", "", "", "",
                                                         "", "", "", "", ""]], date=tpex_date),
    }


def main() -> int:
    # 1. 日期轉換
    ok(W._roc_to_iso("1151013") == "2026-10-13", "民國 7 碼日期")
    ok(W._roc_to_iso("20261014") == "2026-10-14", "西元 8 碼日期")
    ok(W._roc_to_iso("2026/10/14") == "2026-10-14", "西元斜線日期")
    ok(W._roc_to_iso("") is None and W._roc_to_iso("abc") is None, "認不得的日期回 None 不拋錯")
    ok(W._style("美式價外") == "美式" and W._style("歐式") == "歐式" and W._style("") is None
       and W._style("美式與歐式") is None, "備註判斷美式／歐式，兩者都有或都沒有回 None")

    # 2. 解析
    raw = raw_fixture()
    snap = W.build(raw)
    b = snap["basic_twse"][0]
    ok(b["strike"] == 52.5 and b["strike_orig"] == 53.0 and abs(b["ratio"] - 0.065) < 1e-12, "上市基本資料：履約價、行使比例（每仟單位÷1000）")
    ok(b["expiry"] == "2027-10-04" and b["last_trade"] == "2027-09-30" and b["style"] == "美式", "上市基本資料：日期與美式")
    t = snap["basic_tpex"][0]
    ok(t["strike"] == 52.5 and t["style"] == "歐式" and "除息" in (t["remark"] or ""), "全形括號欄位名也認得、備註原文保留")
    ok(snap["issue_tpex"]["700019"]["underlying_code"] == "3707" and snap["issue_tpex"]["700019"]["ratio"] == 0.013,
       "tpex_warrant_issue：標的代號與行使比例")
    q = snap["quotes_twse_call"]
    ok(q[0]["close"] == 0.68 and q[0]["bid"] == 0.71 and q[0]["und_close"] == 36.25 and q[0]["underlying"] == "2409",
       "上市收盤：收盤、買價、標的代號與收盤")
    ok(q[1]["close"] is None and q[1]["bid"] == 0.10, "沒成交的收盤記 None（不是 0），買賣價照記")
    ok(snap["quotes_tpex"][0]["close"] is None and snap["quotes_tpex"][0]["ask"] == 0.55, "上櫃收盤 ---- 記 None")
    ok(snap["underlying_tpex"] == {"3707": 150.5}, "上櫃標的價只留有權證掛的標的")

    # 3. 寫檔前驗證
    ok(W.check("2026-10-14", raw, snap) == [], "日期一致、各表非空 → 通過")
    raw2 = raw_fixture(twse_title_date="115年10月13日")
    errs = W.check("2026-10-14", raw2, W.build(raw2))
    ok(any("twse_call" in e for e in errs), "上市 title 日期不符 → 擋下")
    raw3 = raw_fixture(tpex_date="20261013")
    errs = W.check("2026-10-14", raw3, W.build(raw3))
    ok(any("tpex_ww" in e for e in errs), "上櫃回應日期不符 → 擋下")
    raw4 = raw_fixture()
    raw4["twse_basic"] = []
    errs = W.check("2026-10-14", raw4, W.build(raw4))
    ok(any("basic_twse" in e for e in errs), "空表 → 擋下")
    raw5 = raw_fixture()
    raw5["tpex_ww"]["tables"][1]["fields"] = [f for f in TPEX_F if f != "最後買價"]
    try:
        W.build(raw5)
        ok(False, "缺欄位要拋錯")
    except KeyError:
        ok(True, "缺欄位（最後買價）→ 拋 KeyError，不默默寫 None")

    # 4. 寫檔
    with tempfile.TemporaryDirectory() as td:
        meta = W.write("2026-10-14", snap, Path(td))
        d = Path(td) / "2026-10-14"
        back = json.loads(gzip.decompress((d / "quotes_twse_call.json.gz").read_bytes()))
        ok(back == snap["quotes_twse_call"] and meta["counts"]["basic_twse"] == 2
           and (d / "meta.json").exists() and not (d / "_titles.json.gz").exists(), "gzip 寫檔可讀回、meta 計數正確、不寫內部欄位")

    # 5. 封鎖：第一個請求回 429 → 記封鎖、拋 Blocked、不再發第二個請求
    calls, blocked = [], []
    fake_req = types.SimpleNamespace(get=lambda url, **kw: calls.append(url) or types.SimpleNamespace(status_code=429))
    fake_rl = types.SimpleNamespace(_rate_limit_wait_or_raise=lambda src: None,
                                    _rate_limit_record_block=lambda src, code, d="": blocked.append((src, code)))
    saved = {k: sys.modules.get(k) for k in ("requests", "backfill_price_history_gaps")}
    sys.modules["requests"], sys.modules["backfill_price_history_gaps"] = fake_req, fake_rl
    try:
        with tempfile.TemporaryDirectory() as td:
            try:
                W.fetch_all("2026-10-14", Path(td) / "raw")
                ok(False, "429 要拋 Blocked")
            except W.Blocked:
                ok(len(calls) == 1 and blocked == [("twse_openapi", 429)], "429 → 記封鎖 twse_openapi、只發 1 次、拋 Blocked")
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v

    # 6. 先.一三二-3：tpex_basic 連線中斷（重試後仍斷）→ 其他 6 個來源照抓、照寫，meta 記原因
    class ChunkErr(Exception):
        pass
    calls2 = []

    def fake_get(url, params=None, **kw):
        calls2.append((url, params))
        if url.endswith("mopsfin_t187ap37_O"):
            raise ChunkErr("Connection broken: 10054")
        name = next(n for n, _s, u, pf in W.REQUESTS if u == url and pf("2026-10-14") == params)
        js = raw_fixture()[name]
        return types.SimpleNamespace(status_code=200, json=lambda js=js: js, content=b"x", text="")
    fake_req2 = types.SimpleNamespace(get=fake_get, exceptions=types.SimpleNamespace(
        ConnectionError=ChunkErr, ChunkedEncodingError=ChunkErr))
    fake_rl2 = types.SimpleNamespace(_rate_limit_wait_or_raise=lambda src: None,
                                     _rate_limit_record_block=lambda *a, **k: None)
    saved = {k: sys.modules.get(k) for k in ("requests", "backfill_price_history_gaps")}
    sys.modules["requests"], sys.modules["backfill_price_history_gaps"] = fake_req2, fake_rl2
    old_wait, W.RETRY_WAIT_SEC = W.RETRY_WAIT_SEC, 0
    try:
        with tempfile.TemporaryDirectory() as td:
            failed = {}
            raw6 = W.fetch_all("2026-10-14", Path(td) / "raw", failed)
            ok(set(failed) == {"tpex_basic"} and len(raw6) == 6 and len(calls2) == 8,
               "tpex_basic 連線中斷 → 重試 1 次後略過，其他 6 個照抓（共 8 次請求，不多打）")
            snap6 = W.build(raw6)
            ok("basic_tpex" not in snap6 and "quotes_twse_call" in snap6 and "underlying_tpex" in snap6,
               "缺來源不產出對應檔，其餘照解析")
            ok(W.check("2026-10-14", raw6, snap6) == [], "部分來源時，已抓到的照常驗證通過")
            meta6 = W.write("2026-10-14", snap6, Path(td), failed=failed)
            d6 = Path(td) / "2026-10-14"
            ok(meta6.get("partial") is True and "tpex_basic" in meta6["failed_sources"]
               and meta6["missing_files"] == ["basic_tpex"] and not (d6 / "basic_tpex.json.gz").exists()
               and (d6 / "quotes_twse_call.json.gz").exists(), "meta 記 partial／失敗原因／缺檔，成功的檔照寫")
            # 同一天重跑：已抓的不重抓，只補失敗的那個
            calls2.clear()
            failed2 = {}
            W.fetch_all("2026-10-14", Path(td) / "raw", failed2)
            ok(len(calls2) == 2 and all(u.endswith("mopsfin_t187ap37_O") for u, _ in calls2),
               "同日重跑只補抓失敗的來源（已存原始回應不重抓）")
    finally:
        W.RETRY_WAIT_SEC = old_wait
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v

    ok(len(W.REQUESTS) == 7, "每天固定 7 次請求")
    print(f"\n{'全部通過' if not FAIL else f'失敗 {len(FAIL)} 項'}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
