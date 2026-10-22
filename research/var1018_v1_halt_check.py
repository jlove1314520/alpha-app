"""先.一三〇-3 ③ 輔助診斷：剩下「未涵蓋」的股票，缺口是「缺資料」還是「官方確認停止買賣」（零請求）。

做法：讀 var1018_v1_coverage_recompute.json 的 uncovered 清單，逐檔重建價格日期（FinMind ∪ 官方日檔 ∪ 上櫃逐檔，
同 recompute），找出超過 MAX_GAP_TD 的中段缺口與尾端早停區間；區間內每個營業日：
  - 上市與上櫃全市場日檔都已抓（ok 或 no_data），且該股兩邊都沒列 → official_absent（官方當天沒有這檔＝停止買賣／
    全額交割停牌等；資料完整，只是沒交易）
  - 任一邊還沒抓 → pending（等 var1018_v1_official_fill.py 抓完再看）
  - 只有一邊日檔有資料（上櫃 2007-07 前 before_source_start、或某邊當日 0 列）且該股不在 → no_official_source
    （官方日檔無法佐證是停牌，照缺資料算）
區間內全部營業日都是 official_absent 的區間，判為「官方確認停牌」。

**本腳本不改涵蓋率定義與 95% 門檻**（PREREG V1 第 33～34 行），只多給一個輔助數字：
「若官方確認停牌的區間不算缺口，涵蓋率會是多少」，供 Cowork／總司令判斷要不要修 PREREG 定義。
不讀 2025+ 任何檔案，不計算任何報酬。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import var1018_v1_coverage_recompute as R  # noqa: E402

V, F, OFF = R.V, R.F, R.OFF
OUT = V.D / "var1018_v1_halt_check.json"


def day_state(d: pd.Timestamp) -> dict:
    s = {}
    for src in ("twse", "tpex"):
        p = OFF / src / f"{d.strftime('%Y%m%d')}.json"
        if not p.exists():
            s[src] = None
            continue
        j = json.loads(p.read_text(encoding="utf-8"))
        s[src] = (j.get("status"), j.get("rows") or {})
    return s


def classify_interval(code: str, a: pd.Timestamp, b: pd.Timestamp, cache: dict) -> str:
    """a、b 為缺口兩端（有價格的日子或下市日），檢查兩者之間的營業日。"""
    kinds = set()
    for d in pd.bdate_range(a + pd.Timedelta(days=1), b - pd.Timedelta(days=1)):
        if d not in cache:
            cache[d] = day_state(d)
        s = cache[d]
        tw, tp = s["twse"], s["tpex"]
        if tw is None or tp is None:
            kinds.add("pending")
            continue
        if tw[0] != "ok" and tp[0] != "ok":
            continue  # 兩邊都沒資料＝休市（上櫃起點前且上市休市也落在這裡）
        if code in tw[1] or code in tp[1]:
            kinds.add("listed_no_price")  # 有列但合併後仍判缺（理論上不該出現）
        elif tw[0] == "ok" and tp[0] == "ok":
            kinds.add("official_absent")
        else:
            # 只有一邊有資料（上櫃 2007-07 前 before_source_start、或某邊當日 0 列）→ 無法佐證是停牌
            kinds.add("no_official_source")
    if not kinds:
        return "official_absent"
    for k in ("pending", "listed_no_price", "no_official_source"):
        if k in kinds:
            return k
    return "official_absent"


def main() -> int:
    rec = json.loads(R.OUT.read_text(encoding="utf-8"))
    off, _ = R.official_index()
    cache: dict = {}
    rows = []
    for u in rec["uncovered"]:
        c = u["code"]
        fm = set()
        if V.cached("TaiwanStockPrice", c):
            d = F.load_dev("TaiwanStockPrice", c, V.FETCH_START, V.FETCH_END)
            if not d.empty:
                fm = set(pd.to_datetime(d["date"]))
        t = sorted(x for x in (fm | off.get(c, set())) if V.T0 - pd.Timedelta(days=10) <= x <= V.END)
        end = pd.Timestamp(u["end"])
        t = [x for x in t if x <= end]
        bad = []
        for a, b in zip(t, t[1:]):
            if len(pd.bdate_range(a, b)) - 1 > V.MAX_GAP_TD:
                bad.append(("gap", a, b))
        if (end - t[-1]).days > 20:
            bad.append(("tail", t[-1], end + pd.Timedelta(days=1)))
        ivs = [{"kind": k, "from": str(a.date()), "to": str(b.date()), "td": len(pd.bdate_range(a, b)) - 1,
                "class": classify_interval(c, a, b, cache)} for k, a, b in bad]
        allc = {iv["class"] for iv in ivs}
        verdict = "official_halt_only" if allc == {"official_absent"} else (
            "pending" if "pending" in allc else "data_missing")
        rows.append({"code": c, "delisted": u["delisted"], "verdict": verdict, "intervals": ivs})
    n, ncov = rec["n_universe_t0"], rec["n_covered"]
    nd = rec["n_delisted_in_universe"]
    ndc = round(rec["delisted_coverage"] * nd)
    halt = [r for r in rows if r["verdict"] == "official_halt_only"]
    halt_d = [r for r in halt if r["delisted"]]
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "based_on_recompute": rec["generated_at"], "recompute_partial": rec["partial"],
        "n_uncovered": len(rows),
        "verdict_counts": {k: sum(1 for r in rows if r["verdict"] == k)
                           for k in ("official_halt_only", "pending", "data_missing")},
        "coverage_prereg_definition": {"universe": rec["universe_coverage"], "delisted": rec["delisted_coverage"]},
        "coverage_if_official_halt_not_gap_AUXILIARY": {
            "universe": round((ncov + len(halt)) / n, 4), "delisted": round((ndc + len(halt_d)) / nd, 4)},
        "note": "輔助數字不是 PREREG 定義、不得拿來登記；要改定義須 Cowork 審＋總司令裁示",
    }
    OUT.write_text(json.dumps({**summary, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    for r in rows:
        if r["verdict"] != "official_halt_only":
            print(r["code"], r["delisted"], r["verdict"], [(i["kind"], i["from"], i["to"], i["td"], i["class"])
                                                          for i in r["intervals"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
