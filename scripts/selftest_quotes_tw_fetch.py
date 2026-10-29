"""`.github/scripts/fetch_quotes_tw.py` 合成自測（2026-10-30 先.一三五-1cb）。

零外部請求：`fetch_batch`／`load_universe_codes`／`load_tse_code_set` 換假函式、`OUT_PATH` 換暫存檔。
測：報價回退順序（成交→委買→委賣→昨收）、tse/otc 重複時保留非 stale、data_type 判定、
一檔都沒抓到時不覆寫上一份（1cb 修正點）且照舊非 0 結束。

跑法：python scripts/selftest_quotes_tw_fetch.py
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception as e:  # 十二節：守門員自身失敗只降級成警告
    print(f"[警告] reconfigure 失敗：{e}")

SCRIPT = Path(__file__).resolve().parent.parent / ".github" / "scripts" / "fetch_quotes_tw.py"
spec = importlib.util.spec_from_file_location("fetch_quotes_tw_selftest", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


# 1. 回退順序
check("成交價優先", m.resolve_price({"z": "100", "b": "99_98", "y": "95"}) == (100.0, False))
check("無成交取委買第一檔", m.resolve_price({"z": "-", "b": "-_99.5_99", "y": "95"}) == (99.5, False))
check("無委買取委賣", m.resolve_price({"z": "-", "a": "101_102", "y": "95"}) == (101.0, False))
check("只有昨收標 stale", m.resolve_price({"z": "-", "y": "2,410.00"}) == (2410.0, True))
check("全無回 None", m.resolve_price({}) == (None, True))


def run_main(raw, existing):
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "quotes_tw.json"
        if existing is not None:
            out.write_text(existing, encoding="utf-8")
        m.OUT_PATH = out
        m.load_universe_codes = lambda: ["2330", "6488"]
        m.load_tse_code_set = lambda: {"2330"}
        m.fetch_batch = lambda codes, tse: raw
        code = 0
        try:
            m.main()
        except SystemExit as e:
            code = e.code or 0
        text = out.read_text(encoding="utf-8") if out.exists() else None
        return code, text


# 2. 正常：tse/otc 重複時保留非 stale
raw = [
    {"c": "2330", "n": "台積電", "z": "-", "y": "1000", "d": "20261030", "t": "13:30:00"},
    {"c": "2330", "n": "台積電", "z": "1010", "y": "1000", "d": "20261030", "t": "13:30:00"},
    {"c": "6488", "n": "環球晶", "z": "-", "y": "500", "d": "20261029", "t": "08:00:00"},
]
code, text = run_main(raw, None)
doc = json.loads(text) if text else {}
q = doc.get("quotes", {})
check("正常寫檔 exit 0", code == 0 and text is not None)
check("重複代號保留非 stale", q.get("2330", {}).get("price") == 1010.0 and q["2330"]["stale"] is False)
check("漲跌與幅度", q.get("2330", {}).get("change") == 10.0 and q["2330"].get("change_pct") == 1.0)
check("昨收頂替標 stale", q.get("6488", {}).get("stale") is True)
check("有即時檔 data_type=intraday", doc.get("meta", {}).get("data_type") == "intraday")

# 3. 全部只有昨收 → prev_close
code, text = run_main([{"c": "2330", "z": "-", "y": "1000", "d": "20261029"}], None)
check("全昨收 data_type=prev_close", json.loads(text)["meta"]["data_type"] == "prev_close")

# 4. 一檔都沒抓到：不覆寫上一份、非 0 結束（1cb）
prev = json.dumps({"fetched_at": "2026-10-30T05:00:00+00:00", "quotes": {"2330": {"price": 1000}}})
code, text = run_main([], prev)
check("全失敗非 0 結束", code != 0)
check("全失敗不覆寫上一份", text == prev)
code, text = run_main([{"c": "2330", "z": "-"}], prev)
check("有回應但全無價格也不覆寫", code != 0 and text == prev)
code, text = run_main([], None)
check("全失敗且原本無檔不產生空檔", text is None)

print(f"\n{'全過' if not fails else '失敗 ' + str(len(fails)) + ' 項'}（共 {14} 項）")
sys.exit(1 if fails else 0)
