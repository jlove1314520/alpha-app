"""`HYPOTHESIS_QUEUE.md` #57 全市場當沖比重截面離散度速度（Day-Trading Ratio
Dispersion Velocity）第1關 sanity（2026-09-08 馬拉松第441輪，TW軌）。

**佇列脈絡**：`【2026-09-07 Cowork 更正一】#53～#57`「五條的執行順序」#57排
第一位（#53/#54/#55已結案FAIL，#56撤案）。逐檔回填（`backfill_day_trading_
detail.py`）已於本輪確認2,609/2,609＝100%完成（`data/raw_twse_day_trading_
detail/TWTASU_detail_*.parquet`）。三個維度：(a) 訊號來源＝每日逐檔當沖
成交值占該股當日成交值比重的截面標準差（二階，交易行為強度而非價格/資金
流向，與#53/#54/#55不同源，且跟全市場單一比重版`#37`不同的是這裡是**個股
層級截面二階量**而非市場總量單一序列）、(b) 水位版z(dt_disp_t)與速度版
dt_disp_t/mean(dt_disp_{t-20..t-1})-1並列、(c) 連續曝險縮放（本輪只做
sanity，留待下一關）。

**曝險方向（事前綁定，跟#53/#54/#55一致，不得事後翻號）**：當沖比重截面
離散度急升＝投機資金押注收窄至少數題材股（結構脆弱、過熱訊號集中）
-> 未來報酬應偏低（該降曝險）。

**分子定義（方法論假設，沿用#37既有慣例，非本輪新創）**：`twse_day_trading_
client.py`docstring已記載`#37`把「當沖賣出成交數量+資券互抵成交數量」合計
近似當日全市場現股當沖成交量；本條目是同一個資料源的個股層級**成交值**版，
比照同一套合併慣例：`dt_value_{i,t} = day_trade_sell_value_{i,t} +
margin_offset_value_{i,t}`（兩者皆為TWTASU逐檔欄位，見`twse_day_trading_
client.py::fetch_day_trading_detail_day()`），`dt_ratio_{i,t} = dt_value_
{i,t} / money_{i,t}`（分母沿用`turnover_concentration_gate54.py::
_load_money_long()`同一批`TaiwanStockPrice.Trading_money`快取，與#54同一個
分母，相關係數比較才有意義）。抽樣核對（2024-01-02 2330）：dt_value=
12,433,000+370,752,000=383,185,000，money=16,549,619,798，dt_ratio=2.32%，
量級合理（藍籌股當沖比重偏低，非離群值）。

**4碼普通股過濾**：跟#55同一套規則（`code`欄位可能含ETF/權證等非4碼數字
代碼），過濾後才能算截面統計量。

**與#53/#54/#55相關係數檢查**：`CLAUDE.md`「同家族因子只能算一個獨立
發現」通則，本輪一併算出，不留給下一輪。
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from cross_sectional_dispersion_gate53 import (
    _expanding_percentile,
    _load_taiex_close,
    KNOWN_CRISIS_WINDOWS,
)
from turnover_concentration_gate54 import _load_money_long

DETAIL_DIR = Path(__file__).parent / "data" / "raw_twse_day_trading_detail"
MIN_STOCKS_PER_DATE = 300
VEL_WINDOW = 20
PCTILE_WARMUP = 60
FORWARD_HORIZON = 20
GATE53_CSV = Path(__file__).parent / "data" / "cross_sectional_dispersion_gate53.csv"
GATE54_CSV = Path(__file__).parent / "data" / "turnover_concentration_gate54.csv"
GATE55_CSV = Path(__file__).parent / "data" / "institutional_flow_dispersion_gate55.csv"
FOUR_DIGIT_RE = re.compile(r"^[0-9]{4}$")


def _filter_4digit(df: pd.DataFrame, col: str = "stock_id") -> pd.DataFrame:
    return df[df[col].str.match(FOUR_DIGIT_RE)]


def _load_day_trading_detail_long() -> pd.DataFrame:
    """回傳long-form DataFrame(columns=date, stock_id, dt_value)，逐檔當沖
    成交值合計（當沖賣出成交金額+資券互抵成交金額），已濾成4碼普通股。
    每個TWTASU_detail_*.parquet是單一交易日的全市場逐檔快照（跟#55的T86
    結構相同，逐日讀取，單檔壞掉不拖垮整體）。"""
    files = sorted(DETAIL_DIR.glob("TWTASU_detail_*.parquet"))
    frames = []
    n_ok, n_err, n_empty = 0, 0, 0
    for f in files:
        try:
            df = pd.read_parquet(f, columns=["date", "code", "day_trade_sell_value", "margin_offset_value"])
        except Exception as e:  # noqa: BLE001 -- 單日檔案壞掉不拖垮整體
            print(f"  {f.name}: read ERROR ({e}), dropping")
            n_err += 1
            continue
        if df.empty:
            n_empty += 1
            continue
        df = df.rename(columns={"code": "stock_id"})
        df = _filter_4digit(df)
        if df.empty:
            n_empty += 1
            continue
        df["date"] = pd.to_datetime(df["date"])
        df["dt_value"] = df["day_trade_sell_value"].fillna(0.0) + df["margin_offset_value"].fillna(0.0)
        frames.append(df[["date", "stock_id", "dt_value"]])
        n_ok += 1
    print(f"TWTASU逐檔detail檔案載入結果: ok={n_ok} err={n_err} empty(無4碼普通股列)={n_empty} 總檔案數={len(files)}")
    if not frames:
        raise RuntimeError("no valid day trading detail snapshot loaded")
    out = pd.concat(frames, ignore_index=True)
    out = out.dropna(subset=["date", "stock_id", "dt_value"])
    out = out.drop_duplicates(subset=["date", "stock_id"], keep="last")
    return out


def build_dt_dispersion_series() -> pd.DataFrame:
    """回傳index=date的DataFrame，欄位dt_disp/n_t/vel/level_pctile/
    vel_pctile。全程只用截至當下(含當日)的資料。"""
    dt = _load_day_trading_detail_long()
    money = _load_money_long()
    money = _filter_4digit(money)
    print(f"當沖detail 4碼普通股列數={len(dt)}，money 4碼普通股列數={len(money)}")

    merged = dt.merge(money, on=["date", "stock_id"], how="inner")
    print(f"當沖detail x money inner merge後共同(date,stock_id)列數={len(merged)}")
    merged = merged[merged["money"] > 0]
    merged["f"] = merged["dt_value"] / merged["money"]
    # 當沖成交值理論上不會超過該股當日成交值本身（|f|<=1），留寬鬆邊界到
    # 5.0容許少量統計時點差異（跟#53排除>500%單日報酬、#55排除|f|>=5.0
    # 同一個精神），排除明顯的資料錯誤而非靜默保留離群值。
    n_before = len(merged)
    merged = merged[merged["f"] < 5.0]
    n_extreme = n_before - len(merged)
    print(f"排除dt_ratio>=5.0的離譜值: {n_extreme}/{n_before} 列（{100 * n_extreme / n_before:.2f}%）")

    grouped = merged.groupby("date")["f"].agg(dt_disp="std", n_t="count").reset_index()
    grouped = grouped.sort_values("date").reset_index(drop=True)

    n_unusable = int((grouped["n_t"] < MIN_STOCKS_PER_DATE).sum())
    print(
        f"\n總交易日數={len(grouped)}，n_t<{MIN_STOCKS_PER_DATE}的天數={n_unusable}"
        f"（{100 * n_unusable / len(grouped):.1f}%），標NaN不靜默丟棄"
    )
    grouped.loc[grouped["n_t"] < MIN_STOCKS_PER_DATE, "dt_disp"] = np.nan

    disp = grouped["dt_disp"].to_numpy()
    n = len(disp)
    vel = np.full(n, np.nan)
    for t in range(n):
        if np.isnan(disp[t]):
            continue
        window = disp[max(0, t - VEL_WINDOW):t]
        window = window[~np.isnan(window)]
        if len(window) < VEL_WINDOW:
            continue
        m = window.mean()
        if m <= 0:
            continue
        vel[t] = disp[t] / m - 1.0

    grouped["vel"] = vel
    grouped["level_pctile"] = _expanding_percentile(disp, PCTILE_WARMUP)
    grouped["vel_pctile"] = _expanding_percentile(vel, PCTILE_WARMUP)
    return grouped


def sanity_check_1_descriptive(df: pd.DataFrame) -> dict:
    valid_disp = df["dt_disp"].dropna()
    valid_vel = df["vel"].dropna()
    stats = {
        "n_days_total": len(df),
        "n_days_valid_disp": len(valid_disp),
        "dt_disp_mean": float(valid_disp.mean()),
        "dt_disp_std": float(valid_disp.std()),
        "dt_disp_min": float(valid_disp.min()),
        "dt_disp_max": float(valid_disp.max()),
        "n_t_min": int(df["n_t"].min()),
        "n_t_mean": float(df["n_t"].mean()),
        "n_t_max": int(df["n_t"].max()),
        "n_days_valid_vel": len(valid_vel),
        "vel_mean": float(valid_vel.mean()),
        "vel_std": float(valid_vel.std()),
    }
    print("\n=== sanity 1: 描述統計（非退化性） ===")
    for k, v in stats.items():
        print(f"  {k} = {v}")
    non_degenerate = stats["dt_disp_std"] > 0 and stats["vel_std"] > 0 and stats["n_days_valid_vel"] > 500
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


def correlation_check_vs_prior_gates(df57: pd.DataFrame) -> dict:
    """量#57(level/vel)與#53/#54/#55(level/vel)的相關係數，通則性檢查
    （`CLAUDE.md`「同家族因子只能算一個獨立發現」不限單一條目專屬）。
    事前約定門檻|corr|>0.7判定同家族。"""
    print("\n=== 與#53/#54/#55訊號相關係數檢查（同家族判定，事前約定門檻|corr|>0.7） ===")
    out = {}
    for label, path in (("gate53", GATE53_CSV), ("gate54", GATE54_CSV), ("gate55", GATE55_CSV)):
        if not path.exists():
            print(f"  {path} 不存在，跳過（{label}尚未跑過gate1）")
            out[label] = {"skipped": True, "reason": f"{path} missing"}
            continue
        other = pd.read_csv(path, parse_dates=["date"])
        merged = df57[["date", "level_pctile", "vel_pctile"]].merge(
            other[["date", "level_pctile", "vel_pctile"]], on="date", how="inner", suffixes=("_57", f"_{label[-2:]}")
        )
        merged = merged.dropna()
        corr_level = float(merged.iloc[:, 1].corr(merged.iloc[:, 3]))
        corr_vel = float(merged.iloc[:, 2].corr(merged.iloc[:, 4]))
        same_family = abs(corr_level) > 0.7 or abs(corr_vel) > 0.7
        print(f"  vs {label}: n_aligned={len(merged)} corr_level={corr_level:+.4f} corr_vel={corr_vel:+.4f} 同家族={same_family}")
        out[label] = {"n_aligned": len(merged), "corr_level": corr_level, "corr_vel": corr_vel, "same_family": bool(same_family)}
    return out


def main():
    print("=== #57 全市場當沖比重截面離散度速度 第1關 sanity ===")
    df = build_dt_dispersion_series()
    df.to_csv(Path(__file__).parent / "data" / "day_trading_ratio_dispersion_gate57.csv", index=False)

    s1 = sanity_check_1_descriptive(df)
    s2 = sanity_check_2_crisis_windows(df)
    s3 = sanity_check_3_forward_return(df)
    corr = correlation_check_vs_prior_gates(df)

    overall_pass = s1["pass"] and s2["pass"] and s3["pass"]
    print(f"\n=== 三項sanity皆PASS: {overall_pass} ===")
    print("**這是sanity，不是最終PASS/FAIL判定**——下一輪視結果進第2關（隨機控制組，")
    print("依`control_group_standard.py`統一標準+`trial_registry.register_trial()`正式登記）")
    print("或若sanity方向不對則直接判FAIL並記錄。")
    return {"sanity1": s1, "sanity2": s2, "sanity3": s3, "correlation_vs_prior_gates": corr, "sanity_pass": overall_pass}


if __name__ == "__main__":
    main()
