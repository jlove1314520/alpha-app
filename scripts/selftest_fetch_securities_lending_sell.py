"""自測：借券賣出每日抓取 `.github/scripts/fetch_securities_lending_sell.py`（先.一三五-1bo）。

`requests.get` 換成假回應、節流函式換成空函式、`OUT_PATH` 換暫存檔：零外部請求、不動真實 data/。
模擬 R（paper_18）讀的 `securities_lending_history.json` 由這支的輸出累積而來，這裡確認：
TWT93U 用位置（群組 B，index 8～13）取借券欄位、不被重複欄名「前日餘額」誤導；
429 只打一次、記封鎖、不重試；兩邊都失敗時保留既有檔、不用空資料覆蓋。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
import fetch_securities_lending_sell as S  # noqa: E402

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


class Resp:
    def __init__(self, status=200, body=None):
        self.status_code, self._body, self.text = status, body, json.dumps(body, ensure_ascii=False)[:300]

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


FIELDS = ["代號", "名稱", "前日餘額", "賣出", "買進", "現券", "今日餘額", "次一營業日限額",
          "前日餘額", "當日賣出", "當日還券", "當日調整", "當日餘額", "次一營業日可限額", "備註"]
# 2330 用檔頭記載的 2026-09-14 勾稽數字；群組 A 故意填不同值，抓錯位置就會露餡
ROW_2330 = ["2330", "台積電", "1", "2", "3", "4", "5", "6",
            "16,244,514", "318,000", "26,000", "0", "16,536,514", "9,999,000", ""]
TWSE_OK = {"stat": "OK", "date": "20260914", "fields": FIELDS,
           "data": [ROW_2330, ["2317", "鴻海", *["0"] * 6, "--", "", "0", "0", "100", "_", ""],
                    ["   ", "空代號", *["0"] * 13], ["9999", "太短"]]}
TPEX_OK = [{"Date": "1150914", "SecuritiesCompanyCode": "6488", "CompanyName": "環球晶",
            "SBLVolume": "12,000", "SBLAmount": "5,400,000", "ShortSaleVolume": "3,000", "ShortSaleAmount": ""},
           {"Date": "1150914", "SecuritiesCompanyCode": "", "CompanyName": "空"}]

calls: list = []
blocks: list = []


def install(twse, tpex):
    """twse／tpex：Resp 或 Exception。"""
    calls.clear()
    blocks.clear()

    def fake_get(url, **kw):
        calls.append(url)
        r = twse if url == S.TWSE_URL else tpex
        if isinstance(r, Exception):
            raise r
        return r

    S.requests.get = fake_get
    S._rate_limit_wait_or_raise = lambda source: None
    S._rate_limit_record_block = lambda *a, **k: blocks.append(a)


print("情境一：TWT93U 解析")
install(Resp(body=TWSE_OK), Resp(body=TPEX_OK))
tw, tw_date = S.fetch_twse()
r = tw.get("2330") or {}
check("資料日原樣回傳", tw_date == "20260914", tw_date)
check("取群組 B（不是群組 A 的 1～6）", r.get("sbl_prev_balance") == 16244514 and r.get("sbl_sell") == 318000, r)
check("勾稽：前日−還券＋賣出＋調整＝當日餘額",
      r["sbl_prev_balance"] - r["sbl_return"] + r["sbl_sell"] + r["sbl_adjust"] == r["sbl_balance"], r)
check("次一營業日可限額", r.get("sbl_next_day_quota") == 9999000, r)
check("'--'／''／'_' → None，'0' → 0.0", tw["2317"]["sbl_prev_balance"] is None and tw["2317"]["sbl_sell"] is None
      and tw["2317"]["sbl_next_day_quota"] is None and tw["2317"]["sbl_return"] == 0.0, tw["2317"])
check("空代號、欄數不足的列略過", set(tw) == {"2330", "2317"}, set(tw))

print("情境二：TWT93U 異常")
install(Resp(body={"stat": "很抱歉，沒有符合條件的資料!"}), None)
check("stat 非 OK → ({}, None)", S.fetch_twse() == ({}, None))
install(Resp(body={**TWSE_OK, "fields": FIELDS[:10]}), None)
try:
    S.fetch_twse()
    raised = False
except RuntimeError:
    raised = True
check("欄位數 <14 → 拋錯（不猜位置）", raised)
install(Resp(status=429, body={"msg": "too many"}), None)
try:
    S.fetch_twse()
    raised = False
except RuntimeError:
    raised = True
check("429 → 拋錯", raised)
check("429 只送 1 次、不重試", calls == [S.TWSE_URL], calls)
check("429 記封鎖（來源名 twse_twt93u）", blocks and blocks[0][0] == S.TWSE_SOURCE and blocks[0][1] == 429, blocks)

print("情境三：tpex_short_sell 解析")
install(None, Resp(body=TPEX_OK))
tp, tp_date = S.fetch_tpex()
check("民國日期原樣保留", tp_date == "1150914", tp_date)
check("借券賣出量值", tp.get("6488", {}).get("sbl_sell_volume") == 12000
      and tp["6488"]["sbl_sell_amount"] == 5400000, tp.get("6488"))
check("融券賣出金額空字串 → None", tp["6488"]["short_sale_amount"] is None)
check("空代號略過", set(tp) == {"6488"}, set(tp))
install(None, Resp(body=[]))
check("空陣列 → ({}, None)", S.fetch_tpex() == ({}, None))

print("情境四：main() 寫檔與保留既有")
with tempfile.TemporaryDirectory() as td:
    S.OUT_PATH = Path(td) / "securities_lending_sell.json"

    install(Resp(body=TWSE_OK), RuntimeError("連線逾時"))
    rc = S.main()
    doc = json.loads(S.OUT_PATH.read_text(encoding="utf-8"))
    check("單邊成功 → 寫檔、exit 0", rc == 0 and "2330" in doc["twse"] and doc["tpex"] == {}, rc)
    check("失敗那邊記進 errors", any("tpex_short_sell" in e for e in doc["errors"]), doc["errors"])

    before = S.OUT_PATH.read_text(encoding="utf-8")
    install(RuntimeError("x"), RuntimeError("y"))
    rc = S.main()
    check("兩邊都失敗＋有既有 → 不覆蓋、exit 0", rc == 0 and S.OUT_PATH.read_text(encoding="utf-8") == before, rc)

    S.OUT_PATH.unlink()
    rc = S.main()
    check("兩邊都失敗＋沒有既有 → exit 1", rc == 1, rc)

print(f"\n結果：{ok} PASS / {fail} FAIL")
sys.exit(1 if fail else 0)
