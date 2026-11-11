"""先.一五五-3 第二批第 30 批：HQ#31 台指選擇權偏斜 regime → 0050 曝險（零新外部請求；骨架複製第 14 批）。

序列 `data/option_skew_series.csv`（option_skew_gate.py 既有輸出，2015-01～2024-12，結算價反推 IV）。以下為第 14 批原說明，族已換成偏斜：

族（序列都是本機既有對齊檔／快取，觀察日 d 收盤後才知道 → d 之後第 2 個交易日才吃報酬，同第 4／10／12 批 to_daily）：
- vix_level（HQ 常備 VIX 水準）：`data/vix_level_aligned.csv`，月頻觀察（月初），1997-07 起。
- option_oi_pcr_69（HQ#69 台指選擇權未平倉 PCR）：`data/option_oi_pcr_aligned.csv`，signal_date 為台股日，2015 起。
- adr_premium_tsm（#45 台積電 ADR 溢價）：`data/adr_premium_aligned.csv` 只取 TSM，date＝台股收盤日（ADR 用前一個美股收盤），2006 起。
- fut_basis_60（#38／deep_dive_fut_basis_mean_reversion_60d 台指期近月基差 %）：`fut_basis_series.build_basis_series()`
  只讀本機快取（本批執行時封鎖 socket，讀不到就報錯不送請求），2000 起。
不另做 hy_etf_ratio_roc／vix_term_structure_roc（月頻變化率版）：第 4 批 hy_etf_ratio／HQ#76 已掃日頻 21／63 日變化，同一訊號。
轉換（水準／21／63 日變化，月頻為 1／3 個月變化）× 方向 × expanding 百分位門檻 70/80/90 × 避險曝險 × 槓桿 1/1.5/2/3 × 組合止損，
模擬只呼叫第 4 批 run_sim／stats（沿用第 10 批 main）。序列只到 2024 底，2025 起不擇時（曝險 1、照最佳組槓桿與止損持有）。
樣本內最優化（描述性）；非投資建議。
"""
from __future__ import annotations

import json
import os
import socket
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("REAUDIT_END", "2026-12-31")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.argv = [sys.argv[0]]


def _no_net(*a, **k):
    raise OSError("第 14 批零請求：封鎖網路連線")


socket.socket.connect = _no_net  # 讀快取失敗就報錯，不送任何外部請求

import itertools  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import reaudit_batch10_regime_more as B10  # noqa: E402

B4, B5 = B10.B4, B10.B5
D = HERE / "data"
N, KS = B10.N, B10.KS
SIG_END = pd.Timestamp("2024-12-31")


def _obs_family(series_by_name: dict, monthly=False):
    """同第 12 批 _obs_family，另支援月頻轉換；2025 起沒有新訊號 → 不擇時（曝險 1），不拿舊值頂替。"""
    out, i0 = [], N
    end_i = int(np.searchsorted(B10.DATES.to_numpy(), np.datetime64(SIG_END), side="right")) + 1
    for name, s in series_by_name.items():
        s = s.dropna().sort_index()
        s = s[~s.index.duplicated(keep="last")]
        for tname, pct in B4.transforms(s, monthly=monthly):
            p, first = B4.to_daily(pct.dropna())
            p = np.array(p, dtype=float, copy=True)
            p[end_i:] = np.nan
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


def fam_vix_level():
    return _obs_family({"vix_level": _csv("vix_level_aligned.csv", "vix_level")}, monthly=True)


def fam_oi_pcr():
    return _obs_family({"oi_pcr": _csv("option_oi_pcr_aligned.csv", "oi_pcr", "signal_date")})


def fam_adr_tsm():
    df = pd.read_csv(D / "adr_premium_aligned.csv", parse_dates=["date"])
    df = df[df["ticker"] == "TSM"]
    return _obs_family({"tsm_adr_premium": df.set_index("date")["premium"].astype(float)})


def fam_basis():
    import fut_basis_series
    b = fut_basis_series.build_basis_series()
    return _obs_family({"basis_pct": b.set_index("date")["basis_pct"].astype(float)})


def fam_skew():
    df = pd.read_csv(D / "option_skew_series.csv", parse_dates=["date"]).set_index("date")
    return _obs_family({"skew": df["skew"].astype(float), "put_iv": df["put_iv"].astype(float)})


FAMS = [
    ("option_skew_31", "HQ#31 台指選擇權偏斜（價外賣權 IV − 價外買權 IV）／價外賣權 IV → 0050", fam_skew),
]

B10.FAMS = FAMS
B10.OUT_JSON = D / "reaudit_batch3_batch30.json"
B10.MK_B, B10.MK_E = "<!-- BATCH3-B30-BEGIN -->", "<!-- BATCH3-B30-END -->"
_orig_render = B10.render


def render(out):
    _orig_render(out)
    txt = B10.MD.read_text(encoding="utf-8")
    a, b = txt.split(B10.MK_B)[0], txt.split(B10.MK_B, 1)[1]
    blk, rest = b.split(B10.MK_E, 1)
    blk = blk.replace("## 13. 第二批第 10 批 其餘 regime 族 → 0050（先.一五五-3 ③，`research/reaudit_batch10_regime_more.py`，零新外部請求）",
                      "### 33. 第二批第 30 批 HQ#31 台指選擇權偏斜 → 0050（先.一五五-3 ③，`research/reaudit_batch30_option_skew.py`，零新外部請求）")
    blk = blk.replace("（美國失業率：公布日之後第 2 個交易日）", "（收盤後才知道：觀察日之後第 2 個交易日）")
    blk = blk.replace("相關／離散度族用 #133 抽樣 236 檔（今天回看的名冊，有存活者偏誤）。",
                      "**序列只到 2024 底，2025 起不擇時（曝險 1×、照最佳組槓桿與止損），「2025 起」欄只是同槓桿持有、不代表訊號表現。** "
                      "")
    blk = blk.replace("batch3_b5_b10_*.png", "batch3_b5_b30_*.png")
    blk = blk.replace("曲線 `research", "候選欄另加條件：Calmar 要同時贏同期 0050 與同槓桿不擇時。曲線 `research")
    B10.MD.write_text(a + B10.MK_B + blk + B10.MK_E + rest, encoding="utf-8")


B10.render = render
_orig_plot = B5.plot
B5.plot = lambda name, *a, **k: _orig_plot(name.replace("b10_", "b30_"), *a, **k)


def write_candidates(out):
    d = json.loads(B10.CAND.read_text(encoding="utf-8")) if B10.CAND.exists() else {"candidates": []}
    keep = [c for c in d.get("candidates", []) if not str(c.get("id", "")).startswith("B30R-")]
    new = []
    for f in out["families"]:
        b = f.get("best_by_calmar")
        seg = f.get("best_seg_2015_2024") or {}
        if not b or f.get("rank", 99) > 10 or (b.get("trades") or 0) < 20:
            continue
        bars = [x["calmar"] for x in (f.get("buy_hold_0050_same_period"), f.get("buy_hold_same_leverage_no_timing")) if x and x.get("calmar") is not None]
        if bars and b["calmar"] <= max(bars):
            continue
        note = ["樣本內最優化（偏樂觀）", "regime→0050", "訊號序列只到 2024 底，上紙上前要先接每日更新的原始資料"]
        if b["L"] > 2:
            note.append(f"{b['L']:g}× 超過台股融資上限，紙上要改槓桿 ETF／期貨或降到 2× 以下")
        new.append({"id": f"B30R-{f['family']}", "factor": f["family"], "source": "先.一五五-3 第二批第 30 批（選擇權偏斜 regime→0050）",
                    "status": "候選（待 先.一五四 系列建每日訊號產生器才上紙上）", "rank_in_table": f["rank"],
                    "params": {k: v for k, v in b.items() if k not in ("cagr", "mdd", "sharpe", "trades", "win_rate", "calmar", "violates_survival")},
                    "backtest_period": f"{f['start']}～2024-12-31（訊號），持有到 {f['end']}",
                    "backtest_2015_2024": {k: round(v, 4) for k, v in seg.items()},
                    "from_2025_same_params": None,
                    "full_period_same_params": {"cagr": round(b["cagr"], 4), "mdd": round(b["mdd"], 4), "sharpe": round(b["sharpe"], 2),
                                                "win_rate": None if b["win_rate"] is None else round(b["win_rate"], 3), "trades": b["trades"]},
                    "violates_survival_extended": False, "notes": "；".join(note)})
    d["candidates"] = sorted(keep + new, key=lambda c: c.get("rank_in_table", 99))
    d["generated_at"] = datetime.now().isoformat(timespec="seconds")
    B10.CAND.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    B4.prog(f"候選欄新增第 30 批 {len(new)} 支：" + "、".join(c["factor"] for c in new) + f"；總數 {len(d['candidates'])}")


B10.write_candidates = write_candidates

if __name__ == "__main__":
    B10.main()
