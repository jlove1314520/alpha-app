# -*- coding: utf-8 -*-
"""`.github/scripts/fetch_quotes_tw.py` 的回歸測試（2026-09-05 新增）。

存在的理由：`_num()` 的千分位逗號處理被修過兩次——2026-09-04 修好之後又在某次
rebase/autostash 中無聲消失，害台積電/聯發科這種股價 ≥1000 的股票整整一天沒有走勢線
（`sparkline_error='not_available:empty'`）。沒有測試的修正等於沒有修。

跑法：`python research/fetch_quotes_tw_test.py`（不連網路，純解析邏輯）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / ".github" / "scripts" / "fetch_quotes_tw.py"
spec = importlib.util.spec_from_file_location("fetch_quotes_tw", SCRIPT)
fq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fq)


def test_num_handles_thousands_separator():
    """TWSE STOCK_DAY 對 ≥1000 元的股票回傳 '2,410.00' 這種帶千分位的字串。"""
    assert fq._num("2,410.00") == 2410.0, "千分位逗號沒有被去掉（台積電走勢線消失的根因）"
    assert fq._num("18,490.00") == 18490.0, "五位數股價（如 5274）也要能解析"
    assert fq._num("256.00") == 256.0
    assert fq._num("1,234,567") == 1234567.0
    print("test_num_handles_thousands_separator PASS")


def test_num_edge_cases():
    for empty in (None, "", "-"):
        assert fq._num(empty) is None, f"{empty!r} 應該是 None"
    assert fq._num("abc") is None
    assert fq._num(123.5) == 123.5
    print("test_num_edge_cases PASS")


def test_is_stock_code_filters_warrants():
    """權證/特別股不該進查詢清單（2026-09-04 quotes.yml 卡死的根因）。"""
    assert fq._is_stock_code("2330") and fq._is_stock_code("0050") and fq._is_stock_code("00878")
    assert not fq._is_stock_code("081408") and not fq._is_stock_code("2887I") and not fq._is_stock_code("")
    print("test_is_stock_code_filters_warrants PASS")


def test_resolve_price_prefers_traded_price():
    assert fq.resolve_price({"z": "2,410.00", "y": "2,390.00"}) == (2410.0, False)
    assert fq.resolve_price({"z": "-", "b": "2,405.00_2,404.00", "y": "2,390.00"}) == (2405.0, False)
    assert fq.resolve_price({"z": "-", "y": "2,390.00"}) == (2390.0, True)
    assert fq.resolve_price({"z": "-"}) == (None, True)
    print("test_resolve_price_prefers_traded_price PASS")


def test_source_keeps_comma_fix_and_no_per_stock_sparkline():
    """原始碼層級斷言（不連網路），釘住兩件事：
    (1) 千分位逗號處理還在——這個修正曾在 rebase 中無聲消失兩次，害 >=1000 元股票價格變 None；
    (2) 逐檔抓 sparkline 的舊架構沒有被改回來（走勢線一律走 data/sparklines.json）。"""
    src = SCRIPT.read_text(encoding="utf-8")
    assert 'float(str(v).replace(",", ""))' in src, "千分位逗號處理不見了（>=1000元股票的價格會變成 None）"
    for gone in ("def fetch_sparkline_20d", "def fetch_stock_day_month", "SPARKLINE_TIME_BUDGET_SEC ="):
        assert gone not in src, f"{gone} 又回來了——逐檔抓 STOCK_DAY 的舊架構已被 data/sparklines.json 取代"
    assert "build_sparklines" in src, "註解應指向新的走勢線來源，讓接手的人找得到"
    print("test_source_keeps_comma_fix_and_no_per_stock_sparkline PASS")


def main() -> int:
    tests = [test_num_handles_thousands_separator, test_num_edge_cases,
             test_is_stock_code_filters_warrants, test_resolve_price_prefers_traded_price,
             test_source_keeps_comma_fix_and_no_per_stock_sparkline]
    failed = []
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed.append((t.__name__, str(e)))
            print(f"{t.__name__} FAIL: {e}")
        except Exception as e:  # noqa: BLE001
            failed.append((t.__name__, f"{type(e).__name__}: {e}"))
            print(f"{t.__name__} ERROR: {type(e).__name__}: {e}")
    print()
    if failed:
        print(f"=== {len(failed)}/{len(tests)} 項測試FAIL ===")
        for n, m in failed:
            print(f"  - {n}: {m}")
        return 1
    print(f"=== 全部{len(tests)}項測試PASS ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
