"""先.一五五-3 第二批第 12 批：市場內部籌碼／交易結構指標 → 0050 曝險（零新外部請求）。

族（序列都是本機既有對齊檔，觀察日 d 盤後才知道 → d 之後第 2 個交易日才吃報酬，同第 4 批 to_daily）：
- day_trading_ratio_37：#37 全市場現股當沖比重（`data/day_trading_ratio_aligned.csv`，2015-04 起）。
- inst_concentration_hhi：法人買賣超集中度 HHI（`data/institutional_concentration_hhi_aligned.csv`，2012-07 起）。
- inst_concentration_top10：法人買賣超前 10 檔占比（`data/institutional_concentration_top10_aligned.csv`）。
- turnover_concentration_54：#54 成交值集中度 HHI（`data/turnover_concentration_gate54.csv` 的 conc 欄，涵蓋率不足日已是 NaN）。
轉換×方向×expanding 百分位門檻×避險曝險×槓桿×組合止損，同第 4／10 批；模擬只呼叫第 4 批 run_sim／stats。
序列只到 2024 底（原試驗建檔時截止），2025 起延長要重抓原始資料，本批未延長：2025 起訊號停在最後一個值（ffill），
所以 2025 起分段只是「最後狀態持有」，不代表訊號在 2025 起的表現——照實揭露、該段不拿來排名。
樣本內最優化（描述性）；非投資建議。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("REAUDIT_END", "2026-12-31")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.argv = [sys.argv[0]]

import itertools  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import reaudit_batch10_regime_more as B10  # noqa: E402

B4, B5 = B10.B4, B10.B5
D = HERE / "data"
N, KS = B10.N, B10.KS
SIG_END = pd.Timestamp("2024-12-31")


def _obs_family(series_by_name: dict):
    """觀察日序列 → to_daily（d 之後第 2 個交易日）→ 百分位門檻格子；只在訊號期間內（≤ 2024 底後第 2 個交易日）擇時，之後滿倉 1×。"""
    out, i0 = [], N
    end_i = int(np.searchsorted(B10.DATES.to_numpy(), np.datetime64(SIG_END), side="right")) + 1
    for name, s in series_by_name.items():
        s = s.dropna().sort_index()
        for tname, pct in B4.transforms(s, monthly=False):
            p, first = B4.to_daily(pct.dropna())
            p = np.array(p, dtype=float, copy=True)
            p[end_i:] = np.nan  # 2025 起沒有新訊號：不擇時（曝險 1），不拿舊值頂替
            i0 = min(i0, first)
            for direction, q, k in itertools.product((1, -1), (0.7, 0.8, 0.9), KS):
                off = (p > q) if direction == 1 else (p < 1 - q)
                e = np.where(np.isnan(p), 1.0, np.where(off, k, 1.0))
                out.append(({"series": name, "transform": tname, "riskoff_when": "高" if direction == 1 else "低",
                             "pct_threshold": q, "riskoff_exposure": k}, e))
    return out, i0


def _csv(fn, col, date_col="date"):
    df = pd.read_csv(D / fn, parse_dates=[date_col])
    return df.set_index(date_col)[col].astype(float)


def fam_day_trading():
    return _obs_family({"daytrade_ratio": _csv("day_trading_ratio_aligned.csv", "ratio")})


def fam_inst_hhi():
    return _obs_family({"inst_hhi": _csv("institutional_concentration_hhi_aligned.csv", "conc_raw")})


def fam_inst_top10():
    return _obs_family({"inst_top10": _csv("institutional_concentration_top10_aligned.csv", "conc_raw")})


def fam_turnover():
    df = pd.read_csv(D / "turnover_concentration_gate54.csv", parse_dates=["date"]).set_index("date")
    return _obs_family({"turnover_hhi": df["conc"].astype(float), "turnover_top20": df["top20_share"].where(df["conc"].notna()).astype(float)})


FAMS = [
    ("day_trading_ratio_37", "#37 全市場現股當沖比重 → 0050", fam_day_trading),
    ("inst_concentration_hhi", "法人買賣超集中度 HHI → 0050", fam_inst_hhi),
    ("inst_concentration_top10", "法人買賣超前 10 檔占比 → 0050", fam_inst_top10),
    ("turnover_concentration_54", "#54 成交值集中度 → 0050", fam_turnover),
]

# 沿用第 10 批 main()（只換族、輸出檔、標記）；render 的標題／候選前綴在下面另寫
B10.FAMS = FAMS
B10.OUT_JSON = D / "reaudit_batch3_batch12.json"
B10.MK_B, B10.MK_E = "<!-- BATCH3-B12-BEGIN -->", "<!-- BATCH3-B12-END -->"
_orig_render = B10.render


def render(out):
    for f in out["families"]:
        if f.get("best_by_calmar"):
            f["curve_png"] = f.get("curve_png")
    _orig_render(out)
    txt = B10.MD.read_text(encoding="utf-8")
    a, b = txt.split(B10.MK_B)[0], txt.split(B10.MK_B, 1)[1]
    blk, rest = b.split(B10.MK_E, 1)
    blk = blk.replace("## 13. 第二批第 10 批 其餘 regime 族 → 0050（先.一五五-3 ③，`research/reaudit_batch10_regime_more.py`，零新外部請求）",
                      "## 15. 第二批第 12 批 市場內部籌碼／交易結構指標 → 0050（先.一五五-3 ③，`research/reaudit_batch12_market_internals.py`，零新外部請求）")
    blk = blk.replace("（美國失業率：公布日之後第 2 個交易日）", "（盤後才知道：觀察日之後第 2 個交易日）")
    blk = blk.replace("相關／離散度族用 #133 抽樣 236 檔（今天回看的名冊，有存活者偏誤）。",
                      "**序列只到 2024 底，2025 起不擇時（曝險 1×、照最佳組槓桿與止損），「2025 起」欄只是同槓桿持有、不代表訊號表現。**")
    blk = blk.replace("batch3_b5_b10_*.png", "batch3_b5_b12_*.png")
    blk = blk.replace("曲線 `research", "候選欄另加條件：Calmar 要同時贏同期 0050 與同槓桿不擇時（最佳組多半只是極少減碼的 0050）。曲線 `research")
    B10.MD.write_text(a + B10.MK_B + blk + B10.MK_E + rest, encoding="utf-8")


B10.render = render
_orig_plot = B5.plot
B5.plot = lambda name, *a, **k: _orig_plot(name.replace("b10_", "b12_"), *a, **k)


def write_candidates(out):
    d = json.loads(B10.CAND.read_text(encoding="utf-8")) if B10.CAND.exists() else {"candidates": []}
    keep = [c for c in d.get("candidates", []) if not str(c.get("id", "")).startswith("B12R-")]
    new = []
    for f in out["families"]:
        b = f.get("best_by_calmar")
        seg = f.get("best_seg_2015_2024") or {}
        if not b or f.get("rank", 99) > 10 or (b.get("trades") or 0) < 20:
            continue
        # 〔自行裁量〕最佳組多半只是「極少減碼的 0050」，總表名次會虛高；Calmar 要同時贏同期 0050 與同槓桿不擇時才進候選
        bars = [x["calmar"] for x in (f.get("buy_hold_0050_same_period"), f.get("buy_hold_same_leverage_no_timing")) if x and x.get("calmar") is not None]
        if bars and b["calmar"] <= max(bars):
            continue
        note = ["樣本內最優化（偏樂觀）", "regime→0050", "訊號序列只到 2024 底，上紙上前要先接每日更新的原始資料"]
        if b["L"] > 2:
            note.append(f"{b['L']:g}× 超過台股融資上限，紙上要改槓桿 ETF／期貨或降到 2× 以下")
        new.append({"id": f"B12R-{f['family']}", "factor": f["family"], "source": "先.一五五-3 第二批第 12 批（市場內部指標→0050）",
                    "status": "候選（待 先.一五四 系列建每日訊號產生器才上紙上）", "rank_in_table": f["rank"],
                    "params": {k: v for k, v in b.items() if k not in ("cagr", "mdd", "sharpe", "trades", "win_rate", "calmar", "violates_survival")},
                    "backtest_period": f"{f['start']}～2024-12-31（訊號），持有到 {f['end']}",
                    "backtest_2015_2024": {k: round(v, 4) for k, v in seg.items()},
                    "from_2025_same_params": None,
                    "full_period_same_params": {"cagr": round(b["cagr"], 4), "mdd": round(b["mdd"], 4), "sharpe": round(b["sharpe"], 2),
                                                "win_rate": None if b["win_rate"] is None else round(b["win_rate"], 3), "trades": b["trades"]},
                    "violates_survival_extended": False, "notes": "；".join(note)})
    d["candidates"] = sorted(keep + new, key=lambda c: c["rank_in_table"])
    d["generated_at"] = datetime.now().isoformat(timespec="seconds")
    B10.CAND.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    B4.prog(f"候選欄新增第 12 批 {len(new)} 支：" + "、".join(c["factor"] for c in new) + f"；總數 {len(d['candidates'])}")


B10.write_candidates = write_candidates

if __name__ == "__main__":
    B10.main()
