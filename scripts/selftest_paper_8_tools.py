# -*- coding: utf-8 -*-
"""自測：模擬 H 兩支前置工具（先.一三五-1fp）——零外部請求、不碰真實面板。

- research/paper_8_fetch_capred.py：暫存目錄當 PANEL_DIR、monkeypatch `fc._fetch`／`fc.calls_last_hour`。
  ① failed_ids() 只挑錯誤訊息含「無快取 TaiwanStockCapitalReductionReferencePrice/」的檔；
  ② 一檔壞 JSON（build-panel 寫一半）→ 略過並印警告，不崩潰；
  ③ 達 HOURLY_SOFT_CAP 即停（不送請求）、_fetch 例外即停不重試、成功才刪失敗檔。
- research/paper_8_refresh_dividend_yield.py：④ new_values() 缺快取回 {}、原始價空回 {}、收盤 0 或股利缺值回 None。
模型已凍結（10/27），本自測只用合成資料，不寫 research/data/paper_8_train_panel/。
用法：python scripts/selftest_paper_8_tools.py
"""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import paper_8_fetch_capred as CR  # noqa: E402

FAILS = []


def ok(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def _panel(tmp: Path):
    for p in tmp.glob("*"):
        p.unlink()
    (tmp / "1101.json").write_text(json.dumps({"error": f"本機無快取 {CR.DATASET}/1101_2010-01-01_2024-12-31"}), encoding="utf-8")
    (tmp / "1102.json").write_text(json.dumps({"error": f"本機無快取 {CR.DATASET}/1102_2010-01-01_2024-12-31"}), encoding="utf-8")
    (tmp / "2330.json").write_text(json.dumps({"error": "本機無快取 TaiwanStockPrice/2330_x"}), encoding="utf-8")
    (tmp / "2317.json").write_text(json.dumps({"rows": [{"feature_date": "2020-01-02"}]}), encoding="utf-8")


def test_capred():
    real_dir, real_fetch, real_calls = CR.PANEL_DIR, CR.fc._fetch, CR.fc.calls_last_hour
    calls = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        CR.PANEL_DIR = tmp
        try:
            _panel(tmp)
            ok(CR.failed_ids() == ["1101", "1102"], "① failed_ids 只挑減資快取缺的檔")

            (tmp / "9999.json").write_text('{"error": "本機無快取 ' + CR.DATASET + '/99', encoding="utf-8")  # 寫一半
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    ids = CR.failed_ids()
                ok(ids == ["1101", "1102"] and "9999" in buf.getvalue(), "② 壞 JSON 略過並印警告、不崩潰")
            except Exception as e:  # noqa: BLE001
                ok(False, f"② 壞 JSON 讓 failed_ids 崩潰：{type(e).__name__}")
            (tmp / "9999.json").unlink()

            CR.fc.calls_last_hour = lambda *a, **k: CR.HOURLY_SOFT_CAP
            CR.fc._fetch = lambda *a, **k: calls.append(a) or __import__("pandas").DataFrame({"x": [1]})
            with contextlib.redirect_stdout(io.StringIO()):
                CR.main([])
            ok(not calls and (tmp / "1101.json").exists(), "③a 達 HOURLY_SOFT_CAP 即停、不送請求、不刪檔")

            CR.fc.calls_last_hour = lambda *a, **k: 0

            def boom(*a, **k):
                calls.append(a)
                raise RuntimeError("HTTP 402")
            CR.fc._fetch = boom
            with contextlib.redirect_stdout(io.StringIO()):
                CR.main([])
            ok(len(calls) == 1 and (tmp / "1101.json").exists() and (tmp / "1102.json").exists(),
               "③b _fetch 例外即停、不重試、不刪檔")

            calls.clear()
            import pandas as pd
            CR.fc._fetch = lambda *a, **k: calls.append(a) or (pd.DataFrame() if a[1] == "1102" else pd.DataFrame({"x": [1]}))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                CR.main([])
            res = json.loads(buf.getvalue().strip().splitlines()[-1])
            ok([c[1] for c in calls] == ["1101", "1102"] and not (tmp / "1101.json").exists()
               and not (tmp / "1102.json").exists() and (tmp / "2330.json").exists() and (tmp / "2317.json").exists(),
               "③c 成功才刪對應失敗檔、其他檔不動")
            ok(res == {"fetched": 2, "nonempty": 1, "remaining": 0}, f"③d 結果摘要正確 {res}")
            ok(all(c[0] == CR.DATASET and c[2:] == (CR.START, CR.END) for c in calls), "③e cache key 區間 2010-01-01～2024-12-31（不碰 holdout）")
        finally:
            CR.PANEL_DIR, CR.fc._fetch, CR.fc.calls_last_hour = real_dir, real_fetch, real_calls


def test_refresh():
    import numpy as np
    import pandas as pd
    import paper_8_refresh_dividend_yield as R  # 匯入時會擋網路（socket），本自測本來就零請求
    real = (R._cache_path, R.load_dev, R.factors._dividend_yield_ttm_cash)
    with tempfile.TemporaryDirectory() as td:
        exist = Path(td) / "c.json"
        exist.write_text("{}", encoding="utf-8")
        try:
            R._cache_path = lambda *a, **k: Path(td) / "missing.json"
            ok(R.new_values("1101", ["2020-01-02"]) == {}, "④a 缺快取回 {}")
            R._cache_path = lambda *a, **k: exist
            R.load_dev = lambda *a, **k: pd.DataFrame()
            ok(R.new_values("1101", ["2020-01-02"]) == {}, "④b 原始價空回 {}")
            R.load_dev = lambda *a, **k: pd.DataFrame({"date": ["2020-01-02", "2020-01-03", "2020-01-06"], "close": [10.0, 0.0, 20.0]})
            R.factors._dividend_yield_ttm_cash = lambda *a, **k: pd.DataFrame({"pit_date": ["2020-01-03"], "ttm_cash_dividend": [1.0]})
            v = R.new_values("1101", ["2020-01-02", "2020-01-03", "2020-01-06"])
            ok(v.get("2020-01-02") is None and v.get("2020-01-03") is None and abs((v.get("2020-01-06") or 0) - 0.05) < 1e-12,
               f"④c 股利缺值→None、收盤 0→None、正常值＝股利÷收盤 {v}")
            R.factors._dividend_yield_ttm_cash = lambda *a, **k: pd.DataFrame({"pit_date": ["2020-01-01"], "ttm_cash_dividend": [np.nan]})
            v = R.new_values("1101", ["2020-01-02"])
            ok(v == {"2020-01-02": None}, f"④d 股利 NaN→None {v}")
        finally:
            R._cache_path, R.load_dev, R.factors._dividend_yield_ttm_cash = real


def main():
    test_capred()
    test_refresh()
    print(f"\n{'全部通過' if not FAILS else f'{len(FAILS)} 項失敗'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
