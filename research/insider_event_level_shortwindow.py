# -*- coding: utf-8 -*-
"""內部人買入 個股層級事件研究、交易後短窗口（<20日），`PENDING_QUEUE.md`常備.10。

**來源標記更正（誠實記錄，非隱藏）**：`常備.10`的queue文字寫「月營收個股層級
事件研究」，但實際引用的`STRATEGY_GRAVEYARD.md`line約3546「未測個股層級事件
研究、未測交易後短窗口（<20日）」出自`## #75 內部人買入淨額/買方家數`章節
（line 3540），是內部人交易（美股，SEC DERA Form 4），跟月營收（台股）完全
是兩個不同市場/不同資料源——這是先前某輪`[自走補入]`時的來源誤植。本腳本依
`STRATEGY_GRAVEYARD.md`原文實際內容（內部人交易）執行，不是字面上的「月營收」，
理由：查核後只有內部人交易那段文字精確吻合佇列項目描述的兩個缺口（個股層級＋
短窗口），月營收方向這兩個缺口在`常備.8`（bucket中性化連續分數）/既有
`monthly_revenue_event_study.py`（本來就已經是個股層級event-anchored設計，
只是horizon固定20日）已經有更貼近的覆蓋，不吻合「未測」的字面主張。

**這條填的缺口**：`TRIALS_LEDGER.md`#324（`insider_dera_gate1.py`，FAIL）
只測了「issuer x 月」聚合訊號（`net_usd`/`n_buyers`，一整月的內部人買賣加總成
一個月頻cross-sectional觀測），FAIL。本腳本改成**個股層級、逐筆申報事件**（同一
issuer同一filing_date視為一個事件，不跨月聚合）、**短窗口**（t+5/t+10，而非
既有#75/#324固定用的t+20），且**只用開放市場買入交易**（`code='P'`且
`acq_disp='A'`，排除選擇權履約/贈與/處分等非資訊性交易），這是跟#324聚合月頻
設計不同的具體構造，事前預期：短窗口＋事件級精確度可能比整月稀釋後的訊號更
乾淨（資訊消化理論上該發生在申報揭露後的短期內，不是整個月）。

**美股存活者偏誤但書（`CLAUDE.md`七節強制要求，不得省略）**：宇宙來自SEC DERA
歷史申報（不受限於今日還在市的公司），但**價格資料只覆蓋4965/14306
（34.7%）ticker**——`insider_dera_price_fetch.py`用yfinance分批抓取，已下市股
覆蓋率明顯偏低（`insider_dera_price_coverage2.py`既有記錄），本次結果**只代表
有價格覆蓋的子樣本**，非全體DERA宇宙，繼承#75/#324已知的覆蓋缺口，非本腳本
新增問題。

沿用既有元件（不重新發明）：`data/dera_insider/prices/px_*.csv`（既有yfinance
價格快取）、`insider_dera_price_fetch_status.json`（覆蓋狀態）、
`validation.holdout`（TRAIN_END/VAL_END切分，本地日期字串手動比較，不觸碰
`adjusted_price_series`/`pit.py`——美股價格快取不走台股那條PIT管線，是`insider_
dera_panel.py`既有的獨立輕量快取讀取模式）、`monthly_revenue_event_study.
_permutation_null_percentile`（同一套洗牌null邏輯，全域打散signal↔fwd_ret配對）。

判定標準：cheap gate三判準（同號、VAL贏過500次洗牌null>=90.0、樣本數>=30），
standalone bonferroni_n=1。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from monthly_revenue_event_study import _permutation_null_percentile
from trial_registry import register_trial

H = Path(__file__).parent
DATA_DIR = H / "data" / "dera_insider"
PRICE_DIR = DATA_DIR / "prices"
STATUS_FILE = H / "insider_dera_price_fetch_status.json"

TRAIN_END = pd.Timestamp("2020-12-31")
VAL_END = pd.Timestamp("2024-12-31")
# 價格快取抓取時已截斷在2025-01-01前（見insider_dera_price_fetch.py），
# t+10需要10個交易日空間，事件表止於2024-12-15保守留出空間，不逐檔動態判斷。
EVENT_CUTOFF = pd.Timestamp("2024-12-01")
HORIZONS = (5, 10, 20)  # 20日一併印出供跟#324既有結果對照，判準只看5/10（<20日這個缺口本身）
N_PERMUTATIONS = 500
PERM_SEED = 20260923
BASE_ALPHA = 0.10
BONFERRONI_N = 1
MIN_N = 30
MIN_EVENT_USD = 1000.0  # 濾掉幣值極小、可能是資料雜訊的申報列


def _load_transactions() -> pd.DataFrame:
    files = sorted(DATA_DIR.glob("20*q*.csv"))
    frames = []
    for f in files:
        try:
            df = pd.read_csv(f, dtype={"issuer_cik": str}, usecols=[
                "filing_date", "issuer_cik", "ticker", "code", "acq_disp", "shares", "price",
            ])
        except Exception:  # noqa: BLE001 -- 容錯尺度同insider_dera_panel.py既有做法
            continue
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    raw = pd.concat(frames, ignore_index=True)
    raw = raw[(raw["code"] == "P") & (raw["acq_disp"] == "A")].copy()
    raw["filing_date"] = pd.to_datetime(raw["filing_date"], format="%d-%b-%Y", errors="coerce")
    raw["ticker"] = raw["ticker"].astype(str).str.upper().str.strip()
    raw["usd"] = raw["shares"].astype(float) * raw["price"].astype(float)
    raw = raw.dropna(subset=["filing_date", "usd"])
    raw = raw[raw["usd"] > 0]
    return raw


def _build_events(raw: pd.DataFrame) -> pd.DataFrame:
    """同一issuer同一filing_date視為一個事件（個股層級，非跨月聚合）。"""
    ev = raw.groupby(["issuer_cik", "ticker", "filing_date"]).agg(
        event_usd=("usd", "sum"), n_insiders=("usd", "size"),
    ).reset_index()
    ev = ev[ev["event_usd"] >= MIN_EVENT_USD]
    ev = ev[ev["filing_date"] <= EVENT_CUTOFF]
    return ev


def _price_ok_tickers() -> set[str]:
    import json
    st = json.loads(STATUS_FILE.read_text(encoding="utf-8"))["tickers"]
    return {t for t, v in st.items() if v["status"] == "ok"}


def _attach_forward_returns(events: pd.DataFrame, ok_tickers: set[str]) -> pd.DataFrame:
    events = events[events["ticker"].isin(ok_tickers)].copy()
    cache: dict[str, pd.Series] = {}
    max_h = max(HORIZONS)
    rows = []
    for _, r in events.iterrows():
        t = r["ticker"]
        if t not in cache:
            try:
                p = pd.read_csv(PRICE_DIR / f"px_{t}.csv", parse_dates=["Date"])
            except Exception:  # noqa: BLE001
                cache[t] = None
                continue
            cache[t] = p.sort_values("Date").set_index("Date")["adj_close"]
        s = cache[t]
        if s is None or s.empty:
            continue
        # PIT：市場在filing_date才知道這筆申報，進場＝filing_date之後第一個交易日
        after = s[s.index > r["filing_date"]]
        if after.empty:
            continue
        entry_date = after.index[0]
        i = s.index.get_loc(entry_date)
        if i + max_h >= len(s):
            continue
        p0 = s.iloc[i]
        if pd.isna(p0) or p0 <= 0:
            continue
        row = {
            "issuer_cik": r["issuer_cik"], "ticker": t, "filing_date": r["filing_date"],
            "entry_date": entry_date, "event_usd": float(r["event_usd"]),
            "n_insiders": int(r["n_insiders"]),
        }
        ok = True
        for h in HORIZONS:
            ph = s.iloc[i + h]
            if pd.isna(ph):
                ok = False
                break
            row[f"fwd{h}"] = float(ph / p0 - 1)
        if not ok:
            continue
        rows.append(row)
    return pd.DataFrame(rows)


def _period_stats(df: pd.DataFrame, ret_col: str) -> dict:
    n = len(df)
    if n < 10:
        return {"n": n, "ic": float("nan"), "p_value": float("nan")}
    rho, p = spearmanr(df["event_usd"], df[ret_col])
    return {"n": n, "ic": float(rho), "p_value": float(p)}


def _gate_one(events: pd.DataFrame, horizon: int) -> dict:
    ret_col = f"fwd{horizon}"
    train = events[events["entry_date"] <= TRAIN_END]
    val = events[(events["entry_date"] > TRAIN_END) & (events["entry_date"] <= VAL_END)]
    train_stats = _period_stats(train, ret_col)
    val_stats = _period_stats(val, ret_col)
    same_sign = (
        not pd.isna(train_stats["ic"]) and not pd.isna(val_stats["ic"])
        and np.sign(train_stats["ic"]) == np.sign(val_stats["ic"]) and train_stats["ic"] != 0
    )
    val_for_perm = val.rename(columns={"event_usd": "revenue_sue", ret_col: "fwd_ret"})
    null_pct = _permutation_null_percentile(val_for_perm, val_stats["ic"], N_PERMUTATIONS, PERM_SEED)
    required_pct = 100.0 * (1 - BASE_ALPHA / BONFERRONI_N)
    reasons = []
    if train_stats["n"] < MIN_N or val_stats["n"] < MIN_N:
        reasons.append(f"樣本數過少(train_n={train_stats['n']}, val_n={val_stats['n']})")
    if not same_sign:
        reasons.append("train/val正負號不一致")
    if pd.isna(null_pct) or null_pct < required_pct:
        reasons.append(f"null percentile={null_pct:.1f}未過門檻{required_pct:.1f}")
    passes = len(reasons) == 0
    return {
        "horizon": horizon, "train": train_stats, "val": val_stats,
        "same_sign": same_sign, "null_percentile": null_pct, "required_percentile": required_pct,
        "reasons": reasons, "passes": passes,
    }


def main() -> dict:
    print("=== 內部人買入 個股層級事件研究/短窗口，PENDING_QUEUE.md常備.10 ===")
    raw = _load_transactions()
    print(f"開放市場買入交易列數（code=P,acq_disp=A）：{len(raw)}")
    events_all = _build_events(raw)
    print(f"個股層級事件數（issuer x filing_date聚合，event_usd>={MIN_EVENT_USD}）：{len(events_all)}")

    ok_tickers = _price_ok_tickers()
    events = _attach_forward_returns(events_all, ok_tickers)
    print(f"有價格覆蓋且可算前瞻報酬的事件數：{len(events)}"
          f"（ticker覆蓋{len(ok_tickers)}/14306=34.7%，繼承#75/#324既有存活者偏誤缺口）")

    if events.empty:
        out = {"passes": False, "reason": "no_events"}
        register_trial(
            track="hypothesis_queue", name="insider_event_level_shortwindow",
            design="內部人買入個股層級事件研究(非issuer-month聚合)+短窗口(t+5/t+10)，PENDING_QUEUE.md常備.10，"
                   "填補TRIALS_LEDGER#324「未測個股層級事件研究/未測交易後短窗口」缺口",
            result="零可用事件（價格覆蓋或前瞻報酬空間不足）", verdict="FAIL",
            notes="事件表為空，資料層級問題，非訊號本身無效。",
            round_note="DevQueue自走輪次20260923-131601，PENDING_QUEUE.md常備.10獨立交辦項",
            failed_gates=["unknown"],
        )
        return out

    by_horizon = {h: _gate_one(events, h) for h in HORIZONS}
    for h, r in by_horizon.items():
        print(f"\nt+{h}: TRAIN n={r['train']['n']} IC={r['train']['ic']:+.4f} | "
              f"VAL n={r['val']['n']} IC={r['val']['ic']:+.4f} | "
              f"same_sign={r['same_sign']} | null_pct={r['null_percentile']:.1f}"
              f"(需要>={r['required_percentile']:.1f}) | {'PASS' if r['passes'] else 'FAIL'}"
              + (f" {r['reasons']}" if r['reasons'] else ""))

    # 判準只看<20日缺口本身（t+5/t+10）；t+20僅供對照跟#324既有結果比較，不影響判定。
    short_window_pass = all(by_horizon[h]["passes"] for h in (5, 10))
    verdict = "CHEAP_PASS" if short_window_pass else "FAIL"
    print(f"\n=== 判定（t+5與t+10皆須PASS）：{verdict} ===")

    design = (
        "內部人買入個股層級事件研究(issuer x filing_date，非issuer-month聚合)+短窗口(t+5/t+10，"
        "t+20僅供對照)，PENDING_QUEUE.md常備.10，填補TRIALS_LEDGER#324「未測個股層級事件研究/"
        "未測交易後短窗口(<20日)」缺口，僅開放市場買入(code=P,acq_disp=A)，"
        f"事件USD門檻>={MIN_EVENT_USD}，pooled Spearman IC，N_SHUFFLE={N_PERMUTATIONS}。"
    )
    result = "；".join(
        f"t+{h}: TRAIN n={r['train']['n']} IC={r['train']['ic']:+.4f}, "
        f"VAL n={r['val']['n']} IC={r['val']['ic']:+.4f}, null_pct={r['null_percentile']:.1f}"
        for h, r in by_horizon.items()
    )
    notes = (
        f"判準只看t+5/t+10（<20日缺口本身），t+20列印對照供比較#324既有月頻聚合結果。"
        f"t+5 {'PASS' if by_horizon[5]['passes'] else 'FAIL'}"
        + (f"({by_horizon[5]['reasons']})" if by_horizon[5]["reasons"] else "")
        + f"；t+10 {'PASS' if by_horizon[10]['passes'] else 'FAIL'}"
        + (f"({by_horizon[10]['reasons']})" if by_horizon[10]["reasons"] else "")
        + "。美股存活者偏誤但書：價格覆蓋僅34.7%(4965/14306 ticker)，繼承#75/#324已知缺口，"
          "結果僅代表有價格覆蓋子樣本。"
    )
    register_trial(
        track="hypothesis_queue", name="insider_event_level_shortwindow",
        design=design, result=result, verdict=verdict, notes=notes,
        round_note="DevQueue自走輪次20260923-131601，PENDING_QUEUE.md常備.10獨立交辦項",
        failed_gates=(["cheap_gate_precheck"] if verdict == "FAIL" else None),
    )
    return {"by_horizon": by_horizon, "verdict": verdict}


if __name__ == "__main__":
    import json
    result = main()
    out_path = Path(__file__).parent / "insider_event_level_shortwindow_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n結果已寫入 {out_path}")
