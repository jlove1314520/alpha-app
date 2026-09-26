# -*- coding: utf-8 -*-
"""單元測試：holdout 護欄（2026-09-07 Cybex.債務2）。

驗證 `load_full_history()` 預設拒絕、`allow_holdout=True` 會印警告並指名呼叫端，
以及靜態自查 `holdout_leak_audit.py` 的分級不會退化。

**不連網、不抓任何資料**：`_fetch` 被替換成假的，所以就算護欄壞了也不會真的去
拉一份未 cap 的資料下來。

跑法：`python research/holdout_guard_test.py`
"""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout

import pandas as pd

import finmind_client as fc
import holdout_leak_audit as hla
from validation import holdout
from validation.holdout import VAL_END


def test_default_refuses():
    """預設不帶 allow_holdout 就必須拒絕——這是這一項的核心。"""
    called = []
    orig, fc._fetch = fc._fetch, lambda *a, **k: called.append(a) or pd.DataFrame()
    try:
        try:
            fc.load_full_history("TaiwanStockPrice", "2330")
        except RuntimeError as e:
            assert "load_dev()" in str(e), f"錯誤訊息要指出正確替代方案，實際：{e}"
            assert "unlock_holdout_once" in str(e), f"錯誤訊息要指出唯一合法路徑，實際：{e}"
        else:
            raise AssertionError("預設沒帶 allow_holdout 竟然沒拒絕")
        assert not called, "拒絕時不得已經去抓過資料（那樣未 cap 的副本已經進快取了）"
    finally:
        fc._fetch = orig
    print("test_default_refuses PASS")


def test_allow_holdout_warns_and_names_caller():
    """放行時必須大聲，而且要指名是哪個檔案哪一行——「有人繞過了」查不下去。"""
    orig, fc._fetch = fc._fetch, lambda *a, **k: pd.DataFrame({"date": ["2025-06-01"]})
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            df = fc.load_full_history("TaiwanStockPrice", "2330", allow_holdout=True)
        out = buf.getvalue()
        assert "HOLDOUT WARNING" in out, out
        assert "holdout_guard_test.py" in out, f"警告要指名呼叫端檔案，實際：{out}"
        assert "unlock_holdout_once" in out, "警告要講清楚這不等於解鎖"
        assert len(df) == 1, "放行時要真的回傳資料"
    finally:
        fc._fetch = orig
    print("test_allow_holdout_warns_and_names_caller PASS")


def test_load_dev_still_caps():
    """回歸防線：正規入口照樣 cap 在 VAL_END，不因為這次改動鬆掉。"""
    orig = fc._fetch
    fc._fetch = lambda *a, **k: pd.DataFrame(
        {"date": ["2020-01-01", VAL_END, "2025-06-01"], "close": [1, 2, 3]})
    try:
        df = fc.load_dev("TaiwanStockPrice", "2330")
        assert df["date"].max() <= VAL_END, f"load_dev 竟然放行了 {df['date'].max()}"
        assert len(df) == 2, df
    finally:
        fc._fetch = orig
    print("test_load_dev_still_caps PASS")


def test_audit_classifies_and_finds_no_uncapped_loader():
    """自查本身的回歸防線。

    重點不是「發現數要等於幾」（程式碼會長，數字一定會變），而是兩件**性質**：
    1. 沒有任何未經允許的未 cap loader 呼叫（`UNCAPPED_LOADER == 0`）——這一條
       壞掉就是真的有人繞過 cap 了，要當場擋下來。
    2. 分級有在運作：訊息文字裡的日期不會被算進高風險那一格。第一版純文字掃描
       591 筆命中全是註解日期戳記，那種報告沒有人會讀，等於沒有防線。
    """
    rep = hla.audit()
    assert rep["counts"]["UNCAPPED_LOADER"] == 0, \
        f"出現未經允許的未 cap loader 呼叫：{[f for f in rep['findings'] if f['kind'] == 'UNCAPPED_LOADER']}"
    assert rep["counts"]["AFTER_VAL_END_IN_PROSE"] > rep["counts"]["AFTER_VAL_END"], \
        f"分級失效：高風險 {rep['counts']['AFTER_VAL_END']} 不該多於訊息文字 {rep['counts']['AFTER_VAL_END_IN_PROSE']}"
    assert not rep["unparsable"], f"有檔案解析不了，等於沒掃到：{rep['unparsable']}"
    assert rep["val_end"] == VAL_END
    print(f"test_audit_classifies_and_finds_no_uncapped_loader PASS"
          f"（掃 {rep['files_scanned']} 檔，高風險 {rep['counts']['AFTER_VAL_END']} 筆、"
          f"訊息文字 {rep['counts']['AFTER_VAL_END_IN_PROSE']} 筆、未cap呼叫 0 筆）")


def test_allowlist_blocks_non_allowlisted_caller():
    """守.一（2026-09-26總司令裁示）核心驗證：holdout已被#400合法解鎖後
    （`is_holdout_consumed()`為True，這是本專案的真實current state，不是
    模擬），任何不在`ALLOWED_HOLDOUT_READERS`清單內的呼叫端（本測試檔案
    自己就是一個），讀到VAL_END之後的資料仍然必須raise，效果等同從未
    解鎖過。這是「僅限#400」這句裁示能不能被機制真正擋住的唯一驗證點。
    """
    assert holdout.is_holdout_consumed(), (
        "此測試假設holdout已被#400合法解鎖過（本專案的真實狀態）；"
        "若此assert失敗，代表HOLDOUT_LOCK.json遺失或尚未執行過#400，"
        "本測試的前提不成立，須先確認repo狀態"
    )
    df = pd.DataFrame({"date": ["2025-06-01"]})
    try:
        holdout.assert_no_holdout_leakage(df, context="守.一測試：非允許清單呼叫端(本測試檔案自己)")
    except AssertionError as e:
        assert "允許清單" in str(e) or "ALLOWED_HOLDOUT_READERS" in str(e), \
            f"錯誤訊息應說明是被允許清單收窄擋下，實際：{e}"
    else:
        raise AssertionError("非允許清單腳本讀到2025年資料竟然沒有raise——守.一收窄規則失效")
    print("test_allowlist_blocks_non_allowlisted_caller PASS")


def test_allowlist_passes_for_400_script():
    """對照組：#400腳本自己（在ALLOWED_HOLDOUT_READERS清單內）呼叫同一個
    函式、餵同一種2025年資料，必須no-op通過、不得raise——證明收窄規則
    沒有連#400自己都一併擋掉。
    """
    import holdout_2025_dividend_account_test as h400
    h400._self_test_allowlist_passthrough()  # 不raise就是PASS
    print("test_allowlist_passes_for_400_script PASS")


def main() -> int:
    tests = [test_default_refuses, test_allow_holdout_warns_and_names_caller,
             test_load_dev_still_caps, test_audit_classifies_and_finds_no_uncapped_loader,
             test_allowlist_blocks_non_allowlisted_caller, test_allowlist_passes_for_400_script]
    failed = []
    for t in tests:
        try:
            t()
        except Exception as e:
            failed.append((t.__name__, f"{type(e).__name__}: {e}"))
            print(f"{t.__name__} FAIL: {type(e).__name__}: {e}")
    print()
    if failed:
        print(f"=== {len(failed)}/{len(tests)} 項FAIL ===")
        return 1
    print(f"=== 全部{len(tests)}項測試PASS ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
