"""自測：月營收／本益比每日累積 `.github/scripts/update_fundamentals_daily.py`（先.一三五-1bp）。

`_get_retry` 換假回應、`OUT_PATH` 換暫存檔：零外部請求，不碰真的 data/fundamentals.json。
模擬 G（paper_7，2026-11-02 起跑）的 SUE 只讀這支累積的營收，這裡確認：
民國年月解析、仟元×1000、YoY 轉小數、壞列略過、HTML 地雷拋錯、同年月覆蓋與保留月數、一邊失敗不拖垮另一邊。
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
import update_fundamentals_daily as U  # noqa: E402

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


class FakeResp:
    def __init__(self, body, status=200):
        self._body = body
        self.status_code = status
        self.text = json.dumps(body, ensure_ascii=False) if not isinstance(body, str) else body

    def json(self):
        if isinstance(self._body, str):
            raise ValueError("not json")
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def install(routes: dict) -> list:
    """routes：url → 回應物件或 Exception；回傳呼叫紀錄。"""
    calls: list = []

    def fake(url, source, **kw):
        calls.append((url, source))
        v = routes[url]
        if isinstance(v, Exception):
            raise v
        return v

    U._get_retry = fake
    return calls


REV_ROWS = [
    {"公司代號": "2330", "資料年月": "11509", "營業收入-當月營收": "330,000,000", "營業收入-去年同月增減(%)": "25.5"},
    {"公司代號": "1101", "資料年月": "11509", "營業收入-當月營收": "9,000,000", "營業收入-去年同月增減(%)": ""},
    {"公司代號": "", "資料年月": "11509", "營業收入-當月營收": "1"},          # 缺代號
    {"公司代號": "9999", "資料年月": "1159", "營業收入-當月營收": "1"},       # 年月格式不對
    {"公司代號": "8888", "資料年月": "11509", "營業收入-當月營收": "-"},      # 缺營收
]

print("一、解析小工具")
check("民國年月 11509 → (2026, 9)", U._roc_yearmonth("11509") == (2026, 9))
check("民國年月格式不符回 None", U._roc_yearmonth("1159") is None and U._roc_yearmonth("abcde") is None)
check("民國日期 1151029 → 2026-10-29", U._roc_date_to_iso("1151029") == "2026-10-29")
check("民國日期格式不符回 None", U._roc_date_to_iso("115/10/29") is None)
check("_num 千分位／空值", U._num("1,234.5") == 1234.5 and U._num("-") is None and U._num("N/A") is None and U._num("x") is None)

print("二、fetch_revenue（上市）／fetch_revenue_tpex（上櫃）")
install({U.REVENUE_URL: FakeResp(REV_ROWS), U.TPEX_REVENUE_URL: FakeResp(REV_ROWS[:1])})
rev = U.fetch_revenue()
check("只留 2 檔有效列（缺代號／年月錯／缺營收略過）", sorted(rev) == ["1101", "2330"], sorted(rev))
check("仟元×1000", rev["2330"]["revenue"] == 330_000_000_000, rev["2330"])
check("YoY 百分比轉小數", rev["2330"]["yoy"] == 0.255, rev["2330"]["yoy"])
check("YoY 空字串 → None", rev["1101"]["yoy"] is None)
check("年月欄位", (rev["2330"]["year"], rev["2330"]["month"]) == (2026, 9))
check("上櫃同一套解析", U.fetch_revenue_tpex()["2330"]["revenue"] == 330_000_000_000)
install({U.REVENUE_URL: FakeResp("<html>無效路徑</html>")})
try:
    U.fetch_revenue()
    check("HTML（無效路徑地雷）要拋錯", False, "沒拋")
except Exception as e:  # noqa: BLE001
    check("HTML（無效路徑地雷）要拋錯", True, e)
install({U.REVENUE_URL: FakeResp({"msg": "x"})})
try:
    U.fetch_revenue()
    check("回傳 dict（非 list）要拋錯", False, "沒拋")
except RuntimeError:
    check("回傳 dict（非 list）要拋錯", True)

print("三、fetch_ratios")
install({U.RATIOS_URL: FakeResp([{"Code": "2330", "Date": "1151029", "PEratio": "25.1", "PBratio": "7.2", "DividendYield": "1.3"},
                                 {"Code": "", "Date": "1151029"}])})
r = U.fetch_ratios()
check("本益比列解析", r == {"2330": {"date": "2026-10-29", "per": 25.1, "pbr": 7.2, "dividend_yield": 1.3}}, r)

print("四、merge_revenue")
old = [{"year": 2026, "month": m, "revenue": m} for m in range(1, 10)]
latest = {"year": 2026, "month": 9, "revenue": 999}
m8 = U.merge_revenue(old, latest)
check("同年月覆蓋（不重複）", sum(1 for x in m8 if (x["year"], x["month"]) == (2026, 9)) == 1 and m8[-1]["revenue"] == 999)
check("預設只留 8 個月", len(m8) == 8 and m8[0]["month"] == 2, [x["month"] for x in m8])
m26 = U.merge_revenue(old, {"year": 2026, "month": 10, "revenue": 10}, keep=26)
check("keep=26 全留＋新月份 append", len(m26) == 10 and m26[-1]["month"] == 10)
shuffled = [old[5], old[0], old[8]]
mm = U.merge_revenue(shuffled, {"year": 2025, "month": 12, "revenue": 1}, keep=26)
check("跨年排序", [(x["year"], x["month"]) for x in mm] == [(2025, 12), (2026, 1), (2026, 6), (2026, 9)], mm)
check("existing=None", U.merge_revenue(None, latest) == [latest])
check("不改到呼叫端的 list", len(old) == 9 and old[-1]["revenue"] == 9)

print("五、main（暫存檔）")
with tempfile.TemporaryDirectory() as td:
    out = Path(td) / "fundamentals.json"
    U.OUT_PATH = out
    seed = {"fundamentals": {"2330": {"month_revenue": [{"year": 2026, "month": 8, "revenue": 1}],
                                      "revenue_history_scoring": [{"year": 2026, "month": 8, "revenue": 1}],
                                      "ratios": {"per": 1}},
                             "6488": {"month_revenue": [{"year": 2026, "month": 8, "revenue": 5}]}}}
    out.write_text(json.dumps(seed), encoding="utf-8")
    install({U.RATIOS_URL: RuntimeError("逾時"),
             U.REVENUE_URL: FakeResp(REV_ROWS),
             U.TPEX_RATIOS_URL: FakeResp("<html>"),
             U.TPEX_REVENUE_URL: RuntimeError("tpex_openapi 目前處於封鎖冷卻中")})
    U.main()
    got = json.loads(out.read_text(encoding="utf-8"))
    f = got["fundamentals"]
    check("上市營收照寫（8 月＋9 月）", [x["month"] for x in f["2330"]["month_revenue"]] == [8, 9], f["2330"]["month_revenue"])
    check("評分用 26 個月欄位也更新", [x["month"] for x in f["2330"]["revenue_history_scoring"]] == [8, 9])
    check("本益比失敗保留舊值", f["2330"]["ratios"] == {"per": 1})
    check("上櫃營收失敗保留舊值", f["6488"]["month_revenue"] == [{"year": 2026, "month": 8, "revenue": 5}])
    errs = got["meta"]["errors"]
    check("三個失敗都記進 errors", sorted(e.split(":")[0] for e in errs) == ["ratios_tpex", "ratios_twse", "revenue_tpex"], errs)
    check("新上市股（1101）自動建立", "1101" in f and f["1101"]["month_revenue"][0]["revenue"] == 9_000_000_000)

    U.OUT_PATH = Path(td) / "missing.json"
    try:
        U.main()
        check("既有檔不存在要 exit 1", False, "沒結束")
    except SystemExit as e:
        check("既有檔不存在要 exit 1", e.code == 1, e.code)
    check("既有檔不存在不送請求也不建檔", not U.OUT_PATH.exists())

print(f"\n結果：{ok} 過／{fail} 失敗")
sys.exit(1 if fail else 0)
