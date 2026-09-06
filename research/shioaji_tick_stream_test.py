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

# 測試進程內把熱檔預設路徑改到暫存目錄，避免測試把假tick寫進正式的熱檔讓
# alpha_live_server.py誤以為現在有即時資料（新建的TickState讀的是模組常數）。
import tempfile as _tempfile
sq.LIVE_STATE_PATH = sq.Path(_tempfile.gettempdir()) / "alpha_test_live_state.json"
sq.LIVE_PUSH_ENABLED = False  # 既有測試不要真的對正式伺服器送UDP；tick-push有自己的專屬測試
# 2026-09-07（資料一.1）tick落地：測試裡把落地目錄導到暫存目錄，不要讓假tick混進
# 正式的research/data/ticks/（那份資料是要拿去做研究的，混進假資料就毀了）。
sq.RECORDER = sq.tick_recorder.TickRecorder(
    root=sq.Path(_tempfile.gettempdir()) / "alpha_test_ticks", enabled=True)

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


def test_tick_handler_feeds_recorder_with_latest_bidask():
    """2026-09-07（資料一.1）驗證「tick回呼→落地緩衝」這條線真的接上了，
    而且bid/ask是從TickState取到最近一次BidAsk回呼的值——這是落地資料能不能
    拿來估滑價的關鍵，接錯就是一整天白收。"""
    rec = sq.tick_recorder.TickRecorder(root=sq.Path(_tempfile.gettempdir()) / "alpha_test_ticks2",
                                        enabled=True)
    orig, sq.RECORDER = sq.RECORDER, rec
    try:
        state = sq.TickState()
        sq._make_bidask_stk_handler(state, "2330")(_fake_bidask_stk())  # 先有五檔
        sq._make_tick_stk_handler(state, "2330", None)(_fake_tick_stk())  # 再來一筆成交
        assert rec.pending() == 1, f"落地緩衝應有1筆，實際{rec.pending()}"
        buf = rec._buf[("20260903", "2330")][0]
        assert buf["close"] == 1050.0, buf
        assert buf["volume"] == 3, buf
        assert buf["bid"] == 1049.0 and buf["ask"] == 1050.0, f"bid/ask應取自最近一次五檔，實際{buf}"
        assert buf["chg_type"] == 1, buf
        assert buf["ts"].startswith("2026-09-03T09:30:15"), buf
    finally:
        sq.RECORDER = orig
    print("test_tick_handler_feeds_recorder_with_latest_bidask PASS")


def test_recorder_failure_does_not_break_push():
    """落地壞掉不得影響即時推送。用一個record()一定拋例外的假recorder，
    驗證tick handler照樣把state更新完（不是在半路被例外中斷）。"""
    class _Boom:
        def record(self, *a, **k):
            raise RuntimeError("模擬落地爆炸")

    orig, sq.RECORDER = sq.RECORDER, _Boom()
    try:
        state = sq.TickState()
        sq._make_tick_stk_handler(state, "2330", None)(_fake_tick_stk())
        q = state.snapshot()["2330"]
        assert q["last"] == 1050.0, f"落地爆炸不得影響報價更新，拿到{q}"
        assert q["data_type"] == "REALTIME_TICK", q
    finally:
        sq.RECORDER = orig
    print("test_recorder_failure_does_not_break_push PASS")


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


def test_meaningful_quotes_ignores_tick_at_and_volume():
    """2026-09-03緊急修復回歸測試：995次commit洪水的根因是舊版拿整份
    JSON做git diff，tick_at/volume每筆都變導致每次flush都判定「有變動」
    ——這裡直接驗證`_meaningful_quotes()`會忽略這些欄位，只比較真正的
    報價數字（last/change_pct/bid/ask）。"""
    q1 = {"2330": {"last": 1050.0, "change_pct": 1.5, "bid": 1049.0, "ask": 1050.0,
                    "tick_at": "2026-09-03T09:30:15+08:00", "volume_this_tick": 3, "total_volume": 1200}}
    q2 = {"2330": {"last": 1050.0, "change_pct": 1.5, "bid": 1049.0, "ask": 1050.0,
                    "tick_at": "2026-09-03T09:30:16+08:00", "volume_this_tick": 5, "total_volume": 1205}}
    assert sq._meaningful_quotes(q1) == sq._meaningful_quotes(q2), \
        "只有tick_at/volume變動、價格完全相同時，_meaningful_quotes()應該視為相等"
    print("test_meaningful_quotes_ignores_tick_at_and_volume PASS")


def test_meaningful_quotes_detects_real_price_change():
    """反面驗證：last真的變了，_meaningful_quotes()要能偵測到，不能
    矯枉過正變成永遠回傳True（那樣就完全不commit了，一樣是bug）。"""
    q1 = {"2330": {"last": 1050.0, "change_pct": 1.5, "bid": 1049.0, "ask": 1050.0}}
    q2 = {"2330": {"last": 1051.0, "change_pct": 1.6, "bid": 1050.0, "ask": 1051.0}}
    assert sq._meaningful_quotes(q1) != sq._meaningful_quotes(q2), \
        "last/change_pct/bid/ask真的變動時，_meaningful_quotes()應該偵測到差異"
    print("test_meaningful_quotes_detects_real_price_change PASS")


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


def test_kbar_aggregation_per_minute():
    """2026-09-03深夜新增：同一分鐘內多筆tick聚合成一根K（O=第一筆、H/L=極值、
    C=最後一筆、V=累加），下一分鐘另開一根；跨日自動清空。"""
    state = sq.TickState()
    state.live_state_path = None  # 這個測試不碰檔案
    t0 = datetime(2026, 9, 4, 9, 0, 5)
    state.add_tick("2330", 1000.0, 3, t0)
    state.add_tick("2330", 1005.0, 2, t0.replace(second=20))
    state.add_tick("2330", 998.0, 1, t0.replace(second=50))
    state.add_tick("2330", 1002.0, 4, t0.replace(minute=1, second=1))
    bars = state.kbars_snapshot()["2330"]
    assert len(bars) == 2, f"應有2根K，實際{len(bars)}"
    b0, b1 = bars
    assert (b0["t"], b0["o"], b0["h"], b0["l"], b0["c"], b0["v"]) == ("2026-09-04T09:00", 1000.0, 1005.0, 998.0, 998.0, 6), b0
    assert (b1["t"], b1["o"], b1["c"], b1["v"]) == ("2026-09-04T09:01", 1002.0, 1002.0, 4), b1
    state.add_tick("2330", 1010.0, 1, datetime(2026, 9, 5, 9, 0, 0))  # 跨日
    bars2 = state.kbars_snapshot()["2330"]
    assert len(bars2) == 1 and bars2[0]["t"] == "2026-09-05T09:00", "跨日應清空前一天的K"
    state.add_tick("2330", None, 1, t0)  # price None不能炸也不能加bar
    print("test_kbar_aggregation_per_minute PASS")


def test_live_state_hot_file_written_atomically():
    """2026-09-03深夜新增：熱檔內容要同時有quotes/kbars/mode/kbars_mode，且有
    每秒最多一次的節流（第二次緊接著呼叫不寫、force=True才寫）。"""
    import tempfile, json as _json, os
    tmpdir = tempfile.mkdtemp()
    path = sq.Path(tmpdir) / "hot.json"
    state = sq.TickState()
    state.live_state_path = path
    sq._make_tick_stk_handler(state, "2330", None)(_fake_tick_stk(close="1050.0"))
    assert path.exists(), "第一筆tick後熱檔應該已寫出"
    doc = _json.loads(path.read_text(encoding="utf-8"))
    assert doc["mode"] == "hot-file" and doc["kbars_mode"] == "tick-aggregated-1m", doc.keys()
    assert doc["quotes"]["2330"]["last"] == 1050.0
    assert doc["kbars"]["2330"][0]["c"] == 1050.0 and doc["market_status"] == "open"
    assert state.maybe_write_live_state() is False, "1秒內第二次呼叫應被節流"
    assert state.maybe_write_live_state(force=True, market_status="closed") is True
    assert _json.loads(path.read_text(encoding="utf-8"))["market_status"] == "closed"
    assert not (sq.Path(tmpdir) / "hot.json.tmp").exists(), "暫存檔應已被原子替換掉"
    for f in os.listdir(tmpdir):
        os.remove(os.path.join(tmpdir, f))
    os.rmdir(tmpdir)
    print("test_live_state_hot_file_written_atomically PASS")


def test_intraday_flush_is_noop_when_intraday_push_disabled():
    """2026-09-04乙.1：INTRADAY_GIT_PUSH=False時，盤中_flush_and_push()不能寫冷檔、
    不能碰git（這裡把OUT_PATH指到暫存檔、_git換成會記錄呼叫的假函式驗證）。"""
    import tempfile, os
    tmpdir = tempfile.mkdtemp()
    fake_out = sq.Path(tmpdir) / "quotes_sinopac.json"
    calls = []
    orig_out, orig_git, orig_flag = sq.OUT_PATH, sq._git, sq.INTRADAY_GIT_PUSH
    sq.OUT_PATH, sq._git, sq.INTRADAY_GIT_PUSH = fake_out, (lambda args: calls.append(args) or type("R", (), {"returncode": 0})()), False
    try:
        state = sq.TickState(); state.live_state_path = None
        sq._make_tick_stk_handler(state, "2330", None)(_fake_tick_stk())
        sq._flush_and_push(state)  # 盤中
        assert not fake_out.exists(), "盤中不該寫冷檔"
        assert calls == [], f"盤中不該有任何git呼叫：{calls}"
    finally:
        sq.OUT_PATH, sq._git, sq.INTRADAY_GIT_PUSH = orig_out, orig_git, orig_flag
        for f in os.listdir(tmpdir):
            os.remove(os.path.join(tmpdir, f))
        os.rmdir(tmpdir)
    print("test_intraday_flush_is_noop_when_intraday_push_disabled PASS")


def test_tick_push_sends_udp_datagram_with_token():
    """2026-09-04零.2：收到tick後要對LIVE_PUSH_ADDR送一個帶token/key/quote/bar的UDP
    datagram；token檔不存在時要安靜停用（不拋錯）。"""
    import socket, json as _json, tempfile, os
    recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv.bind(("127.0.0.1", 0)); recv.settimeout(2)
    tmpdir = tempfile.mkdtemp(); tok = sq.Path(tmpdir) / ".alpha_live_token"
    tok.write_text("TESTTOKEN123", encoding="utf-8")
    orig_tok = sq.LIVE_TOKEN_PATH
    sq.LIVE_TOKEN_PATH = tok
    try:
        state = sq.TickState(); state.live_state_path = None
        state.push_addr = recv.getsockname()
        sq._make_tick_stk_handler(state, "2330", None)(_fake_tick_stk(close="1050.0"))
        data, _ = recv.recvfrom(65535)
        msg = _json.loads(data.decode("utf-8"))
        assert msg["t"] == "TESTTOKEN123" and msg["key"] == "2330" and msg["event"] == "tick", msg
        assert msg["quote"]["last"] == 1050.0 and msg["bar"]["c"] == 1050.0, msg
        assert state.push_count == 1
        # token檔不存在→停用，不拋錯
        sq.LIVE_TOKEN_PATH = sq.Path(tmpdir) / "missing"
        state2 = sq.TickState(); state2.live_state_path = None; state2.push_addr = recv.getsockname()
        assert state2.push_tick("2330") is False and state2._push_disabled_reason
    finally:
        sq.LIVE_TOKEN_PATH = orig_tok
        recv.close()
        for f in os.listdir(tmpdir):
            os.remove(os.path.join(tmpdir, f))
        os.rmdir(tmpdir)
    print("test_tick_push_sends_udp_datagram_with_token PASS")


def test_resolve_fop_key_maps_actual_month_code_to_near_key():
    """2026-09-04四修.一回歸防線：tick.code是TXFI6/MXFI6這種實際月份碼，訂閱時登記的是
    TXFR1連續別名——必須能對回TXF_NEAR/MXF_NEAR，不能再被靜默丟掉。"""
    m = {"TXFR1": "TXF_NEAR", "2330": "2330"}
    assert sq._resolve_fop_key("TXFR1", m) == "TXF_NEAR"
    assert sq._resolve_fop_key("TXFI6", m) == "TXF_NEAR"
    assert sq._resolve_fop_key("MXFI6", m) == "MXF_NEAR"
    assert sq._resolve_fop_key("EXFI6", m) == "EXF_NEAR"
    assert sq._resolve_fop_key("FXFJ6", m) == "FXF_NEAR"
    assert sq._resolve_fop_key("ZZZI6", m) is None
    print("test_resolve_fop_key_maps_actual_month_code_to_near_key PASS")


def main():
    tests = [
        test_resolve_fop_key_maps_actual_month_code_to_near_key,
        test_tick_push_sends_udp_datagram_with_token,
        test_intraday_flush_is_noop_when_intraday_push_disabled,
        test_kbar_aggregation_per_minute,
        test_live_state_hot_file_written_atomically,
        test_tick_stk_handler_updates_state,
        test_tick_handler_feeds_recorder_with_latest_bidask,
        test_recorder_failure_does_not_break_push,
        test_bidask_stk_handler_updates_state_without_clobbering_tick_fields,
        test_quote_idx_handler_computes_change_pct_from_reference,
        test_callback_exception_does_not_propagate,
        test_build_payload_produces_valid_json_serializable_structure,
        test_meaningful_quotes_ignores_tick_at_and_volume,
        test_meaningful_quotes_detects_real_price_change,
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
