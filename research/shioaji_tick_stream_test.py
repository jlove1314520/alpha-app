# -*- coding: utf-8 -*-
"""單元測試：模擬tick/bidask/quote callback觸發→`TickState`更新→
`_build_payload()`組出正確JSON內容（2026-09-03新增，B34「Shioaji報價
升級為逐筆tick串流」使用者明確要求的驗證項目）。

**刻意不連真正的Shioaji連線、不寫`data/quotes_sinopac.json`、不觸發
git commit/push**——這支測試只驗證`shioaji_quotes.py`裡「callback收到
資料之後怎麼處理」這段自己的邏輯是否正確，不依賴、也不驗證Shioaji SDK
本身的行為（那部分只有下次台股開盤、真的連上模擬環境才能驗證，見
`shioaji_quotes.py`模組docstring「API方法簽章來源」的誠實揭露）。

跑法：`python research/shioaji_tick_stream_test.py`，全部斷言通過才印
「全部PASS」。
"""
from __future__ import annotations

from types import SimpleNamespace
from datetime import datetime, timezone, timedelta

import shioaji_quotes as sq

TW_TZ = timezone(timedelta(hours=8))


def _fake_tick_stk(code="2330", close="1050.0", pct_chg="1.5", price_chg="15.0",
                    volume=3, total_volume=1200, chg_type=1):
    return SimpleNamespace(
        code=code, close=close, pct_chg=pct_chg, price_chg=price_chg,
        volume=volume, total_volume=total_volume, chg_type=chg_type,
        datetime=datetime(2026, 9, 3, 9, 30, 15, tzinfo=TW_TZ),
    )


def _fake_bidask_stk(code="2330", bid_price=None, ask_price=None):
    return SimpleNamespace(
        code=code,
        bid_price=bid_price if bid_price is not None else ["1049.0", "1048.0"],
        ask_price=ask_price if ask_price is not None else ["1050.0", "1051.0"],
    )


def _fake_quote_idx(code="IX0001", close="17850.5", reference="17600.0"):
    return SimpleNamespace(
        code=code, close=close, reference=reference,
        datetime=datetime(2026, 9, 3, 9, 30, 15, tzinfo=TW_TZ),
    )


def test_tick_stk_handler_updates_state():
    state = sq.TickState()
    handler = sq._make_tick_stk_handler(state, "2330", None)
    handler(_fake_tick_stk())

    snap = state.snapshot()
    assert "2330" in snap, "2330應該已經出現在state裡"
    q = snap["2330"]
    assert q["last"] == 1050.0, f"last應該是1050.0，拿到{q['last']}"
    assert q["change_pct"] == 1.5, f"change_pct應該是1.5，拿到{q['change_pct']}"
    assert q["close"] == 1035.0, f"close(前一個參考價)應該是1050.0-15.0=1035.0，拿到{q['close']}"
    assert q["data_type"] == "REALTIME_TICK", f"data_type應該標REALTIME_TICK，拿到{q['data_type']}"
    assert q["volume_this_tick"] == 3
    assert q["total_volume"] == 1200
    print("test_tick_stk_handler_updates_state PASS")


def test_bidask_stk_handler_updates_state_without_clobbering_tick_fields():
    """驗證bidask callback只更新bid/ask兩個欄位，不會把tick callback
    已經寫好的last/change_pct等欄位洗掉——這是`TickState.update()`用
    `dict.update()`局部合併而不是整個物件取代的設計重點，要斷言到。"""
    state = sq.TickState()
    sq._make_tick_stk_handler(state, "2330", None)(_fake_tick_stk())
    sq._make_bidask_stk_handler(state, "2330")(_fake_bidask_stk())

    q = state.snapshot()["2330"]
    assert q["bid"] == 1049.0, f"bid應該是1049.0（bid_price[0]），拿到{q['bid']}"
    assert q["ask"] == 1050.0, f"ask應該是1050.0（ask_price[0]），拿到{q['ask']}"
    assert q["last"] == 1050.0, "bidask更新後last不應該被洗掉"
    assert q["change_pct"] == 1.5, "bidask更新後change_pct不應該被洗掉"
    print("test_bidask_stk_handler_updates_state_without_clobbering_tick_fields PASS")


def test_quote_idx_handler_computes_change_pct_from_reference():
    state = sq.TickState()
    handler = sq._make_quote_idx_handler(state, "TAIEX", "加權指數")
    handler(_fake_quote_idx())

    q = state.snapshot()["TAIEX"]
    assert q["last"] == 17850.5
    assert q["close"] == 17600.0, "指數的close欄位應該存reference(前收基準)"
    expected_pct = round((17850.5 - 17600.0) / 17600.0 * 100.0, 4)
    assert q["change_pct"] == expected_pct, f"change_pct應該是{expected_pct}，拿到{q['change_pct']}"
    assert q["label"] == "加權指數"
    print("test_quote_idx_handler_computes_change_pct_from_reference PASS")


def test_callback_exception_does_not_propagate():
    """callback裡任何例外都不能讓整個訂閱掛掉（見handler內部的
    try/except），這裡塞一個一定會讓getattr/算術失敗的壞tick，斷言
    handler呼叫本身不拋例外，且state保持乾淨（沒有寫入半殘的資料）。"""
    state = sq.TickState()
    handler = sq._make_tick_stk_handler(state, "2330", None)
    broken_tick = SimpleNamespace(code="2330")  # 缺close/pct_chg等欄位
    handler(broken_tick)  # 不應該拋例外
    snap = state.snapshot()
    assert "2330" in snap
    assert snap["2330"]["last"] is None, "缺欄位時last應該誠實留None，不是0或其他預設值"
    print("test_callback_exception_does_not_propagate PASS")


def test_build_payload_produces_valid_json_serializable_structure():
    """驗證`_build_payload()`組出來的dict可以被`json.dumps()`成功序列化
    （不含Shioaji原生型別、datetime等不能直接序列化的物件），這是
    `_flush_and_push()`實際寫檔前那一步，用假資料驗證這段邏輯正確，
    不用真的碰`data/quotes_sinopac.json`。"""
    import json

    state = sq.TickState()
    sq._make_tick_stk_handler(state, "2330", None)(_fake_tick_stk())
    sq._make_bidask_stk_handler(state, "2330")(_fake_bidask_stk())
    sq._make_quote_idx_handler(state, "TAIEX", "加權指數")(_fake_quote_idx())

    payload = sq._build_payload(state)
    serialized = json.dumps(payload, ensure_ascii=False)  # 這行本身失敗就是測試失敗
    reloaded = json.loads(serialized)

    assert reloaded["connected"] is True
    assert reloaded["market_status"] == "open"
    assert set(reloaded["quotes"].keys()) == {"2330", "TAIEX"}
    assert reloaded["quotes"]["2330"]["last"] == 1050.0
    assert reloaded["quotes"]["TAIEX"]["last"] == 17850.5
    print("test_build_payload_produces_valid_json_serializable_structure PASS")


def test_trading_window_boundary():
    """`_is_tw_trading_window()`既有既有的簡化限制（不扣國定假日），這裡
    只驗證最基本的邊界行為沒有被這次改版意外弄壞（升級過程中這個函式
    是直接沿用既有邏輯搬過來，不應該有變化，這裡當回歸防線）。"""
    mon_0829 = datetime(2026, 9, 7, 8, 29, tzinfo=TW_TZ)  # 週一08:29，開盤前1分鐘
    mon_0830 = datetime(2026, 9, 7, 8, 30, tzinfo=TW_TZ)  # 週一08:30，開盤那一刻
    mon_1344 = datetime(2026, 9, 7, 13, 44, tzinfo=TW_TZ)  # 週一13:44，收盤前
    mon_1345 = datetime(2026, 9, 7, 13, 45, tzinfo=TW_TZ)  # 週一13:45，收盤那一刻
    sat_1000 = datetime(2026, 9, 12, 10, 0, tzinfo=TW_TZ)  # 週六，非交易日

    assert sq._is_tw_trading_window(mon_0829) is False
    assert sq._is_tw_trading_window(mon_0830) is True
    assert sq._is_tw_trading_window(mon_1344) is True
    assert sq._is_tw_trading_window(mon_1345) is False
    assert sq._is_tw_trading_window(sat_1000) is False
    print("test_trading_window_boundary PASS")


def main():
    tests = [
        test_tick_stk_handler_updates_state,
        test_bidask_stk_handler_updates_state_without_clobbering_tick_fields,
        test_quote_idx_handler_computes_change_pct_from_reference,
        test_callback_exception_does_not_propagate,
        test_build_payload_produces_valid_json_serializable_structure,
        test_trading_window_boundary,
    ]
    failed = []
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed.append((t.__name__, str(e)))
            print(f"{t.__name__} FAIL: {e}")
        except Exception as e:
            failed.append((t.__name__, f"{type(e).__name__}: {e}"))
            print(f"{t.__name__} ERROR: {type(e).__name__}: {e}")

    print()
    if failed:
        print(f"=== {len(failed)}/{len(tests)} 項測試FAIL ===")
        for name, msg in failed:
            print(f"  - {name}: {msg}")
    else:
        print(f"=== 全部{len(tests)}項測試PASS ===")


if __name__ == "__main__":
    main()
