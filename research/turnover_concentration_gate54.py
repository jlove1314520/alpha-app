"""`HYPOTHESIS_QUEUE.md` #54 成交值集中度速度（Turnover Concentration
Velocity）第1關 sanity（2026-09-08 馬拉松第430輪，TW軌）。

**佇列脈絡**：`HYPOTHESIS_QUEUE.md` #54 條目規格已寫死（2026-09-08），排在
「五條的執行順序」第一位（#53已於round429/hypothesis_queue結案FAIL）。三個
維度：(a) 訊號來源=每日逐檔成交值占比的HHI（二階，金額流向而非價格變動，
與#53的報酬離散度不同源）、(b) 水位版z(conc_t)與速度版
conc_t/mean(conc_{t-20..t-1})-1 並列、(c) 連續曝險縮放（本輪只做sanity，
留待下一關）。

**曝險方向（事前綁定，不得事後翻號）**：成交值集中度急升＝參與面收窄／
資金押注收窄 -> 未來報酬應偏低（廣度惡化 -> 該降曝險）。

**與#53的區別必須在這一關就量出來**：若#54訊號（level或vel）與#53訊號
（同版本）相關係數絕對值>0.7，依`CLAUDE.md`「同家族因子只能算一個獨立
發現」，二者合併計為一個發現，不得分開算兩個獨立候選——即使#53已死也
不影響這一步的必要性（#54仍需獨立走完自己的GATE_SEQUENCE，相關係數只
影響「發現計數」不影響「這條假說本身該不該繼續測」）。

**資料源**：與#53同一批`data/raw/TaiwanStockPrice__*__2010-01-01__2024-12-31
.parquet`快取（`Trading_money`欄，零新增API呼叫），沿用`cross_sectional_
dispersion_gate53.py::_discover_stock_files()`同一套個股候選池過濾規則
（排除6檔非個股聚合列、排除<2000 bytes空快取），確保#53/#54用同一個
分母，相關係數比較才有意義。

**涵蓋率交叉檢查**：`data/raw_twse_market_volume/FMTQIK_*.parquet`
（全市場逐日成交金額，2015-01～2024-12共120個月檔，TWSE官方
`FMTQIK`端點）。樣本Trading_money加總 / 全市場total_value < 80%的
交易日標為不可用（conc設NaN），避免樣本涵蓋率不足的早期年份（2010-2014，
FMTQIK無資料）或涵蓋率不足的日子混進主判定。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from cross_sectional_dispersion_gate53 import (
    _discover_stock_files,
    _expanding_percentile,
    _load_taiex_close,
    KNOWN_CRISIS_WINDOWS,
)

DATA_DIR = Path(__file__).parent / "data" / "raw"
MARKET_VOL_DIR = Path(__file__).parent / "data" / "raw_twse_market_volume"
MIN_STOCKS_PER_DATE = 300
MIN_COVERAGE_RATIO = 0.80
VEL_WINDOW = 20
PCTILE_WARMUP = 60
FORWARD_HORIZON = 20
GATE53_CSV = Path(__file__).parent / "data" / "cross_sectional_dispersion_gate53.csv"


def _load_money_long() -> pd.DataFrame:
    """回傳long-form DataFrame(columns=date, stock_id, money)，逐檔成交值。
    跟`cross_sectional_dispersion_gate53.py::_load_return_long()`同一套
    容錯與過濾（單檔壞掉不拖垮整體），但不算報酬，只取Trading_money。"""
    files = _discover_stock_files()
    frames = []
    n_ok, n_err, n_short = 0, 0, 0
    for i, (sid, path) in enumerate(files):
        try:
            df = pd.read_parquet(path, columns=["date", "Trading_money"])
        except Exception as e:  # noqa: BLE001 -- 跟factor_ic.py同一套容錯
            print(f"  [{i + 1}/{len(files)}] {sid}: read ERROR ({e}), dropping")
            n_err += 1
            continue
        if df.empty or len(df) < 30:
            n_short += 1
            continue
        df = df.dropna(subset=["date", "Trading_money"]).sort_values("date")
        df["date"] = pd.to_datetime(df["date"])
        df = df.drop_duplicates(subset="date", keep="last")
        df = df[df["Trading_money"] > 0]
        sub = pd.DataFrame({"date": df["date"].to_numpy(), "stock_id": sid, "money": df["Trading_money"].to_numpy()})
        frames.append(sub)
        n_ok += 1
    print(f"逐檔載入結果: ok={n_ok} err={n_err} too_short(<30列)={n_short}")
    if not frames:
        raise RuntimeError("no valid stock money series loaded")
    return pd.concat(frames, ignore_index=True)


def _load_market_total_value() -> pd.DataFrame:
    """全市場逐日成交金額（TWSE FMTQIK官方端點既有快取），供涵蓋率交叉檢查。"""
    files = sorted(MARKET_VOL_DIR.glob("FMTQIK_*.parquet"))
    frames = [pd.read_parquet(f, columns=["date", "total_value"]) for f in files]
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    return df.dropna(subset=["total_value"]).drop_duplicates(subset="date", keep="last").sort_values("date")


def build_concentration_series() -> pd.DataFrame:
    """回傳index=date的DataFrame，欄位conc/top20_share/n_t/coverage_ratio/
    vel/level_pctile/vel_pctile。全程只用截至當下(含當日)的資料。"""
    long_df = _load_money_long()

    def _agg(g: pd.DataFrame) -> pd.Series:
        m = g["money"].to_numpy()
        total = m.sum()
        w = m / total
        hhi = float((w ** 2).sum())
        top20 = float(np.sort(w)[::-1][:20].sum())
        return pd.Series({"conc": hhi, "top20_share": top20, "n_t": len(m), "sample_total_money": total})

    grouped = long_df.groupby("date").apply(_agg, include_groups=False).reset_index()
    grouped = grouped.sort_values("date").reset_index(drop=True)

    market = _load_market_total_value()
    grouped = grouped.merge(market, on="date", how="left")
    grouped["coverage_ratio"] = grouped["sample_total_money"] / grouped["total_value"]

    n_unusable_n = int((grouped["n_t"] < MIN_STOCKS_PER_DATE).sum())
    print(
        f"\n總交易日數={len(grouped)}，n_t<{MIN_STOCKS_PER_DATE}的天數={n_unusable_n}"
        f"（{100 * n_unusable_n / len(grouped):.1f}%）"
    )
    grouped.loc[grouped["n_t"] < MIN_STOCKS_PER_DATE, "conc"] = np.nan

    has_coverage = grouped["coverage_ratio"].notna()
    n_low_coverage = int((has_coverage & (grouped["coverage_ratio"] < MIN_COVERAGE_RATIO)).sum())
    n_no_market_data = int((~has_coverage).sum())
    print(
        f"涵蓋率<{MIN_COVERAGE_RATIO:.0%}的天數={n_low_coverage}（{100 * n_low_coverage / len(grouped):.1f}%）；"
        f"FMTQIK無對應資料(通常是2015-01前)的天數={n_no_market_data}（{100 * n_no_market_data / len(grouped):.1f}%）"
    )
    grouped.loc[~has_coverage, "conc"] = np.nan
    grouped.loc[has_coverage & (grouped["coverage_ratio"] < MIN_COVERAGE_RATIO), "conc"] = np.nan

    conc = grouped["conc"].to_numpy()
    n = len(conc)
    vel = np.full(n, np.nan)
    for t in range(n):
        if np.isnan(conc[t]):
            continue
        window = conc[max(0, t - VEL_WINDOW) : t]
        window = window[~np.isnan(window)]
        if len(window) < VEL_WINDOW:
            continue
        m = window.mean()
        if m <= 0:
            continue
        vel[t] = conc[t] / m - 1.0

    grouped["vel"] = vel
    grouped["level_pctile"] = _expanding_percentile(conc, PCTILE_WARMUP)
    grouped["vel_pctile"] = _expanding_percentile(vel, PCTILE_WARMUP)
    return grouped


def sanity_check_1_descriptive(df: pd.DataFrame) -> dict:
    valid_conc = df["conc"].dropna()
    valid_vel = df["vel"].dropna()
    stats = {
        "n_days_total": len(df),
        "n_days_valid_conc": len(valid_conc),
        "conc_mean": float(valid_conc.mean()),
        "conc_std": float(valid_conc.std()),
        "conc_min": float(valid_conc.min()),
        "conc_max": float(valid_conc.max()),
        "top20_share_mean": float(df["top20_share"].dropna().mean()),
        "n_t_min": int(df["n_t"].min()),
        "n_t_mean": float(df["n_t"].mean()),
        "n_days_valid_vel": len(valid_vel),
        "vel_mean": float(valid_vel.mean()),
        "vel_std": float(valid_vel.std()),
    }
    print("\n=== sanity 1: 描述統計（非退化性） ===")
    for k, v in stats.items():
        print(f"  {k} = {v}")
    non_degenerate = stats["conc_std"] > 0 and stats["vel_std"] > 0 and stats["n_days_valid_vel"] > 500
    print(f"  非退化判定: {non_degenerate}")
    stats["pass"] = bool(non_degenerate)
    return stats


def sanity_check_2_crisis_windows(df: pd.DataFrame) -> dict:
    print("\n=== sanity 2: 已知危機期間 level/vel 百分位是否偏高（描述性參考，非主判準） ===")
    unconditional_level = df["level_pctile"].mean()
    unconditional_vel = df["vel_pctile"].mean()
    print(f"  無條件基準: level_pctile_mean={unconditional_level:.3f}  vel_pctile_mean={unconditional_vel:.3f}")
    results = {}
    hits = 0
    for name, (start, end) in KNOWN_CRISIS_WINDOWS.items():
        mask = (df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))
        window = df.loc[mask]
        lvl = window["level_pctile"].mean()
        vel = window["vel_pctile"].mean()
        hit = bool(vel > unconditional_vel)
        hits += int(hit)
        print(
            f"  {name} ({start}~{end}, n={len(window)}): "
            f"level_pctile={lvl:.3f} vel_pctile={vel:.3f}  vel高於基準={hit}"
        )
        results[name] = {"n": len(window), "level_pctile": float(lvl), "vel_pctile": float(vel), "vel_above_baseline": hit}
    print(f"  三個危機窗口中vel_pctile高於無條件基準的窗口數: {hits}/3")
    results["hits"] = hits
    results["unconditional_level"] = float(unconditional_level)
    results["unconditional_vel"] = float(unconditional_vel)
    results["pass"] = hits >= 2
    return results


def sanity_check_3_forward_return(df: pd.DataFrame) -> dict:
    print("\n=== sanity 3: 條件式前瞻20日TAIEX報酬（tertile切分） ===")
    taiex = _load_taiex_close()
    tw_dates = taiex["date"].to_numpy()
    tw_close = taiex["close"].to_numpy()

    rows = []
    for _, r in df.iterrows():
        if np.isnan(r["level_pctile"]) or np.isnan(r["vel_pctile"]):
            continue
        sig_date = np.datetime64(r["date"])
        start_idx = int(np.searchsorted(tw_dates, sig_date, side="right"))
        end_idx = start_idx + FORWARD_HORIZON - 1
        if start_idx >= len(tw_dates) or end_idx >= len(tw_dates):
            continue
        fwd_ret = tw_close[end_idx] / tw_close[start_idx] - 1.0
        rows.append({"date": r["date"], "level_pctile": r["level_pctile"], "vel_pctile": r["vel_pctile"], "fwd_ret": fwd_ret})
    aligned = pd.DataFrame(rows)
    print(f"  對齊後樣本數: {len(aligned)}")

    out = {"n_aligned": len(aligned)}
    for col in ("level_pctile", "vel_pctile"):
        q1, q2 = aligned[col].quantile([1 / 3, 2 / 3])
        low = aligned[aligned[col] <= q1]["fwd_ret"]
        high = aligned[aligned[col] >= q2]["fwd_ret"]
        direction_ok = bool(high.mean() < low.mean())
        print(
            f"  {col}: 低tertile(n={len(low)}) fwd_ret_mean={low.mean():+.4f}  "
            f"高tertile(n={len(high)}) fwd_ret_mean={high.mean():+.4f}  方向正確(高<低)={direction_ok}"
        )
        out[col] = {"low_mean": float(low.mean()), "high_mean": float(high.mean()), "direction_ok": direction_ok}
    out["pass"] = out["level_pctile"]["direction_ok"] or out["vel_pctile"]["direction_ok"]
    return out


def correlation_check_vs_gate53(df54: pd.DataFrame) -> dict:
    """量#54(level/vel)與#53(level/vel)的相關係數。若|corr|>0.7判定同家族，
    依`CLAUDE.md`只能算一個獨立發現——這一步不論#53死活都要做，因為
    HYPOTHESIS_QUEUE.md #54條目寫死「須在sanity關就量出來並記錄」。"""
    print("\n=== 與#53訊號相關係數檢查（同家族判定，事前約定門檻|corr|>0.7） ===")
    if not GATE53_CSV.exists():
        print(f"  {GATE53_CSV} 不存在，跳過（#53尚未跑過gate1）")
        return {"skipped": True, "reason": "gate53 csv missing"}
    df53 = pd.read_csv(GATE53_CSV, parse_dates=["date"])
    merged = df54[["date", "level_pctile", "vel_pctile"]].merge(
        df53[["date", "level_pctile", "vel_pctile"]], on="date", how="inner", suffixes=("_54", "_53")
    )
    merged = merged.dropna()
    print(f"  對齊後共同交易日樣本數: {len(merged)}")
    corr_level = float(merged["level_pctile_54"].corr(merged["level_pctile_53"]))
    corr_vel = float(merged["vel_pctile_54"].corr(merged["vel_pctile_53"]))
    print(f"  level_pctile相關係數(#54 vs #53) = {corr_level:+.4f}")
    print(f"  vel_pctile相關係數(#54 vs #53)   = {corr_vel:+.4f}")
    same_family = abs(corr_level) > 0.7 or abs(corr_vel) > 0.7
    print(f"  同家族判定(|corr|>0.7任一版本): {same_family}")
    if same_family:
        print("  -> 依CLAUDE.md「同家族因子只能算一個獨立發現」，#53/#54計數時合併為一個發現")
    else:
        print("  -> 相關係數未超過門檻，#54維持獨立發現地位（惟仍需獨立通過自己的GATE_SEQUENCE）")
    return {
        "n_aligned": len(merged),
        "corr_level": corr_level,
        "corr_vel": corr_vel,
        "same_family": bool(same_family),
    }


def main():
    print("=== #54 成交值集中度速度 第1關 sanity ===")
    df = build_concentration_series()
    df.to_csv(Path(__file__).parent / "data" / "turnover_concentration_gate54.csv", index=False)

    s1 = sanity_check_1_descriptive(df)
    s2 = sanity_check_2_crisis_windows(df)
    s3 = sanity_check_3_forward_return(df)
    corr = correlation_check_vs_gate53(df)

    overall_pass = s1["pass"] and s2["pass"] and s3["pass"]
    print(f"\n=== 三項sanity皆PASS: {overall_pass} ===")
    print("**這是sanity，不是最終PASS/FAIL判定**——下一輪視結果進第2關（隨機控制組，")
    print("依`control_group_standard.py`統一標準+`trial_registry.register_trial()`正式登記）")
    print("或若sanity方向不對則直接判FAIL並記錄。")
    return {"sanity1": s1, "sanity2": s2, "sanity3": s3, "correlation_vs_gate53": corr, "sanity_pass": overall_pass}


if __name__ == "__main__":
    main()
