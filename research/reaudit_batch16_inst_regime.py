"""先.一五五-3 第二批第 16 批：法人資金流離散度／外資台指期未平倉 → 0050 曝險（零新外部請求）。

族（序列都是本機既有對齊檔／快取，觀察日 d 收盤後才知道 → d 之後第 2 個交易日才吃報酬，同第 4／10／12／14 批 to_daily）：
- institutional_flow_dispersion_55（HQ#55 三大法人買賣超橫斷面離散度）：`data/institutional_flow_dispersion_gate55.csv` 的 flow_disp，2012-05 起。
- fut_inst_foreign_oi（fut_recheck_inst_momentum_highres：外資台指期淨未平倉口數）：本機 FinMind
  `TaiwanFuturesInstitutionalInvestors__TX__2000-01-01__2024-12-31.parquet`（實際 2018-06-05 起），外資多方未平倉口數－空方未平倉口數；
  另做三大法人合計淨未平倉。原試驗是 5 日變化方向，這裡沿用共用轉換（水準／21／63 日變化）。
轉換 × 方向 × expanding 百分位門檻 70/80/90 × 避險曝險 × 槓桿 1/1.5/2/3 × 組合止損，模擬只呼叫第 4 批 run_sim／stats（沿用第 10 批 main）。
序列只到 2024 底，2025 起不擇時（曝險 1、照最佳組槓桿與止損持有）。樣本內最優化（描述性）；非投資建議。
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
    raise OSError("第 16 批零請求：封鎖網路連線")


socket.socket.connect = _no_net  # 讀快取失敗就報錯，不送任何外部請求

import itertools  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import fred_yield_curve_gate as _fg  # noqa: E402

_fg._CACHE_MAX_AGE_SECONDS = 10 ** 10  # 本批零請求：DEXTAUS 只用在美股腿（與 0050 無關），快取過期也讀本機舊檔

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


def fam_flow_disp():
    return _obs_family({"flow_disp": _csv("institutional_flow_dispersion_gate55.csv", "flow_disp")})


def _fut_inst():
    df = pd.read_parquet(D / "raw" / "TaiwanFuturesInstitutionalInvestors__TX__2000-01-01__2024-12-31.parquet")
    df["date"] = pd.to_datetime(df["date"])
    df["net_oi"] = df["long_open_interest_balance_volume"].astype(float) - df["short_open_interest_balance_volume"].astype(float)
    return df


def fam_fut_foreign():
    df = _fut_inst()
    f = df[df["institutional_investors"] == "外資"].set_index("date")["net_oi"]
    t = df.groupby("date")["net_oi"].sum()
    return _obs_family({"foreign_net_oi": f, "three_inst_net_oi": t})


FAMS = [
    ("institutional_flow_dispersion_55", "#55 三大法人買賣超離散度 → 0050", fam_flow_disp),
    ("fut_inst_foreign_oi", "外資／三大法人台指期淨未平倉 → 0050", fam_fut_foreign),
]

B10.FAMS = FAMS
B10.OUT_JSON = D / "reaudit_batch3_batch16.json"
B10.MK_B, B10.MK_E = "<!-- BATCH3-B16-BEGIN -->", "<!-- BATCH3-B16-END -->"
_orig_render = B10.render


def render(out):
    _orig_render(out)
    txt = B10.MD.read_text(encoding="utf-8")
    a, b = txt.split(B10.MK_B)[0], txt.split(B10.MK_B, 1)[1]
    blk, rest = b.split(B10.MK_E, 1)
    blk = blk.replace("## 13. 第二批第 10 批 其餘 regime 族 → 0050（先.一五五-3 ③，`research/reaudit_batch10_regime_more.py`，零新外部請求）",
                      "## 19. 第二批第 16 批 法人資金流離散度／外資台指期淨未平倉 → 0050（先.一五五-3 ③，`research/reaudit_batch16_inst_regime.py`，零新外部請求）")
    blk = blk.replace("（美國失業率：公布日之後第 2 個交易日）", "（收盤後才知道：觀察日之後第 2 個交易日）")
    blk = blk.replace("相關／離散度族用 #133 抽樣 236 檔（今天回看的名冊，有存活者偏誤）。",
                      "**序列只到 2024 底，2025 起不擇時（曝險 1×、照最佳組槓桿與止損），「2025 起」欄只是同槓桿持有、不代表訊號表現。** "
                      "外資台指期部位資料 2018-06 起（FinMind），原試驗的 5 日變化改用共用 21／63 日變化。"
                      "**fut_inst_foreign_oi 訊號期只有 2019-06～2024-12（約 5.5 年、61 次減碼，幾乎全在多頭），「2015～2024」欄實際是 2019-06～2024；全期年化 +40.5% 有一大段來自 2025 起 1.5× 不擇時持有，訊號本身的貢獻要看 2019～2024 那欄（+28.0%／−28.4%，同期 1.5× 不擇時約 MDD −47.6%）。** ")
    blk = blk.replace("batch3_b5_b10_*.png", "batch3_b5_b16_*.png")
    blk = blk.replace("曲線 `research", "候選欄另加條件：Calmar 要同時贏同期 0050 與同槓桿不擇時。曲線 `research")
    B10.MD.write_text(a + B10.MK_B + blk + B10.MK_E + rest, encoding="utf-8")


B10.render = render
_orig_plot = B5.plot
B5.plot = lambda name, *a, **k: _orig_plot(name.replace("b10_", "b16_"), *a, **k)


def write_candidates(out):
    d = json.loads(B10.CAND.read_text(encoding="utf-8")) if B10.CAND.exists() else {"candidates": []}
    keep = [c for c in d.get("candidates", []) if not str(c.get("id", "")).startswith("B16R-")]
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
        if f["family"] == "fut_inst_foreign_oi":
            note.append("訊號期只有 2019-06～2024-12（約 5.5 年、61 次減碼、幾乎全在多頭），全期年化含 2025 起 1.5× 不擇時持有")
        if b["L"] > 2:
            note.append(f"{b['L']:g}× 超過台股融資上限，紙上要改槓桿 ETF／期貨或降到 2× 以下")
        new.append({"id": f"B16R-{f['family']}", "factor": f["family"], "source": "先.一五五-3 第二批第 16 批（法人 regime→0050）",
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
    B4.prog(f"候選欄新增第 16 批 {len(new)} 支：" + "、".join(c["factor"] for c in new) + f"；總數 {len(d['candidates'])}")


B10.write_candidates = write_candidates

if __name__ == "__main__":
    B10.main()
