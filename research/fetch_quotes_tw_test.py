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


def test_source_has_tpex_skip_and_breaker_exemption():
    """兩個曾經在 rebase 中無聲消失的修正，用原始碼層級斷言釘住（沒有網路也能測）：
    (1) 上櫃股不送 STOCK_DAY 請求（`tpex_not_covered`）；
    (2) `stat_not_ok` 不計入連續失敗斷路器。"""
    src = SCRIPT.read_text(encoding="utf-8")
    assert "not_available:tpex_not_covered" in src, "上櫃跳過邏輯不見了（會白吃請求並打開斷路器）"
    assert 'if not (isinstance(e, SparklineFetchError) and e.kind == "stat_not_ok"):' in src, \
        "stat_not_ok 又被計入斷路器了（幾檔沒資料就會關掉整批抓取）"
    assert 'float(str(v).replace(",", ""))' in src, "千分位逗號處理不見了（≥1000元股票會沒有走勢線）"
    print("test_source_has_tpex_skip_and_breaker_exemption PASS")


def main() -> int:
    tests = [test_num_handles_thousands_separator, test_num_edge_cases,
             test_is_stock_code_filters_warrants, test_resolve_price_prefers_traded_price,
             test_source_has_tpex_skip_and_breaker_exemption]
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
