# -*- coding: utf-8 -*-
"""單元測試：`tick_recorder.py` 的緩衝→jsonl→parquet 全流程（2026-09-07 資料一.1）。

**刻意不連 Shioaji、不碰正式的 `research/data/ticks/`**——整份測試在暫存目錄裡跑，
用 `SimpleNamespace` 假 tick 物件模擬回呼傳進來的東西。要驗證的是這支模組自己的
邏輯：欄位有沒有正確抽出來、flush 有沒有 append、壓縮後列數對不對、核對失敗時
jsonl 會不會被保住。

跑法：`python research/tick_recorder_test.py`，全部斷言通過才印「全部PASS」。
"""
from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import tick_recorder as tr


def _tick(ts: str, close="123.5", volume=3, chg_type=2, tick_type=1,
          suspend=False, simtrade=False, intraday_odd=False):
    """假的 TickSTKv1。Shioaji 的價格欄位型別是 str（見 shioaji/_core.pyi），
    這裡刻意也用 str，確保 _num() 真的有在轉。"""
    return SimpleNamespace(datetime=datetime.fromisoformat(ts), close=close, volume=volume,
                           chg_type=chg_type, tick_type=tick_type, suspend=suspend,
                           simtrade=simtrade, intraday_odd=intraday_odd)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="alpha_ticks_test_"))
    orig_root = tr.TICKS_ROOT
    tr.TICKS_ROOT = tmp
    try:
        rec = tr.TickRecorder(root=tmp, enabled=True)

        # ── 1. record() 只進緩衝，不碰磁碟 ────────────────────────────────
        rec.record("2330", _tick("2026-09-07T09:00:01"), bid=123.0, ask=123.5)
        rec.record("2330", _tick("2026-09-07T09:00:02", close="124", volume=5), bid=124.0, ask=124.5)
        rec.record("2454", _tick("2026-09-07T09:00:03", close="1400"))
        assert rec.pending() == 3, f"緩衝應有3筆，實際{rec.pending()}"
        assert not (tmp / "20260907").exists(), "record() 不該碰磁碟"

        # ── 2. flush() 寫成 jsonl，且欄位正確 ────────────────────────────
        n = rec.flush()
        assert n == 3, f"flush 應寫3筆，實際{n}"
        assert rec.pending() == 0, "flush 後緩衝應清空"
        f2330 = tmp / "20260907" / "2330.jsonl"
        lines = f2330.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2, f"2330 應2行，實際{len(lines)}"
        r0 = json.loads(lines[0])
        assert r0["ts"] == "2026-09-07T09:00:01", r0
        assert r0["close"] == 123.5 and isinstance(r0["close"], float), "close 應轉成 float"
        assert r0["volume"] == 3 and r0["bid"] == 123.0 and r0["ask"] == 123.5, r0
        assert r0["chg_type"] == 2 and r0["tick_type"] == 1, r0
        assert r0["suspend"] is False and r0["simtrade"] is False, r0
        r2454 = json.loads((tmp / "20260907" / "2454.jsonl").read_text(encoding="utf-8").splitlines()[0])
        assert r2454["bid"] is None and r2454["ask"] is None, "沒訂 BidAsk 的代號應誠實記 null"

        # ── 3. flush() 是 append，不是覆寫 ───────────────────────────────
        rec.record("2330", _tick("2026-09-07T09:01:00", close="125"))
        rec.flush()
        assert len(f2330.read_text(encoding="utf-8").splitlines()) == 3, "第二次 flush 應 append"

        # ── 4. 空 flush 不報錯也不建檔 ───────────────────────────────────
        assert rec.flush() == 0, "沒東西時 flush 應回 0"

        # ── 5. 停用開關真的不落地 ────────────────────────────────────────
        off = tr.TickRecorder(root=tmp, enabled=False)
        off.record("9999", _tick("2026-09-07T09:02:00"))
        assert off.pending() == 0 and off.flush() == 0, "停用時不該收也不該寫"
        assert not (tmp / "20260907" / "9999.jsonl").exists(), "停用時不該建檔"

        # ── 6. 壞行不害整天壓縮失敗 ─────────────────────────────────────
        with f2330.open("a", encoding="utf-8") as f:
            f.write('{"ts":"2026-09-07T09:0')  # 模擬行程被砍時寫到一半的最後一行

        # ── 7. compact()：jsonl → 單一 parquet，且刪掉 jsonl ────────────
        res = tr.compact("20260907")
        assert res.get("skipped") is None, res
        assert res["rows"] == 4, f"應有 3(2330) + 1(2454) = 4 列，實際{res}"
        assert res["bad_lines"] == 1, f"應剛好跳過 1 行壞資料，實際{res}"
        assert res["deleted"] is True, "壓縮成功後應刪掉 jsonl 目錄"
        assert not (tmp / "20260907").exists(), "jsonl 目錄應已刪除"
        pq_path = tmp / "20260907.parquet"
        assert pq_path.exists() and pq_path.stat().st_size > 0, "應產出 parquet"

        import pyarrow.parquet as pq
        table = pq.read_table(pq_path)
        assert table.num_rows == 4, table.num_rows
        assert table.column_names == ["code", *tr.FIELDS], table.column_names
        codes = table.column("code").to_pylist()
        assert codes.count("2330") == 3 and codes.count("2454") == 1, codes

        # ── 8. 已有 parquet 時不覆蓋（避免重跑把好資料蓋掉）─────────────
        (tmp / "20260907").mkdir()
        (tmp / "20260907" / "1101.jsonl").write_text(
            json.dumps({"ts": "2026-09-07T09:00:00", "close": 1.0}) + "\n", encoding="utf-8")
        res2 = tr.compact("20260907")
        assert res2.get("skipped"), "已有 parquet 應 skip"
        assert (tmp / "20260907").exists(), "skip 時不得刪 jsonl"
        shutil.rmtree(tmp / "20260907")

        # ── 9. 沒有目錄時是 skip 不是例外 ───────────────────────────────
        assert tr.compact("20990101").get("skipped"), "沒有目錄應回 skipped"

        # ── 10. compact_stale_days 只壓非今日 ──────────────────────────
        for day in ("20260905", "20260908"):
            (tmp / day).mkdir()
            (tmp / day / "2330.jsonl").write_text(
                json.dumps({"ts": f"{day[:4]}-{day[4:6]}-{day[6:]}T09:00:00", "close": 1.0,
                            "volume": 1}) + "\n", encoding="utf-8")
        out = tr.compact_stale_days(today="20260908")
        assert [r["day"] for r in out] == ["20260905"], f"只該壓 20260905，實際{out}"
        assert (tmp / "20260905.parquet").exists(), "非今日應已壓成 parquet"
        assert (tmp / "20260908").exists(), "今日的 jsonl 不得被壓掉（還在寫）"

        # ── 11. stat() 回報 parquet 與 jsonl 各自大小 ──────────────────
        st = tr.stat()
        assert "20260907" in st["days"] and "parquet" in st["days"]["20260907"], st
        assert "20260908" in st["days"] and "jsonl" in st["days"]["20260908"], st
        assert st["total_bytes"] > 0, st

        print("全部PASS（11 組斷言）")
        return 0
    finally:
        tr.TICKS_ROOT = orig_root
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
