"""`HYPOTHESIS_QUEUE.md` #55 三大法人買賣超截面離散度速度（Institutional Flow
Dispersion Velocity）第1關 sanity（2026-09-08 hypothesis_queue排程接續）。

**佇列脈絡**：`【2026-09-07 Cowork 更正一】#53～#57`「五條的執行順序」#55排
第一位（#53/#54已結案FAIL，#56撤案）。三個維度：(a) 訊號來源=每日逐檔
三大法人淨買超金額除以當日成交值做規模標準化後的截面標準差（二階，資金流
而非價格變動或金額流向，與#53/#54不同源）、(b) 水位版z(flow_disp_t)與
速度版flow_disp_t/mean(flow_disp_{t-20..t-1})-1並列、(c) 連續曝險縮放
（本輪只做sanity，留待下一關）。

**曝險方向（事前綁定，跟`HYPOTHESIS_QUEUE.md` #55條目一致，不得事後翻號）**：
法人流離散度急升（錢集中到少數股，結構脆弱）-> 未來報酬應偏低（該降曝險）。

**資料缺口已於本佇列前一輪處理完畢**：T86原缺2024-06-25~12-31共136個交易日，
已用`backfill_t86.py`回填完成（見`HYPOTHESIS_QUEUE.md` #55條目「回填已完成」
段落），本輪VAL期不需截斷，全程沿用既有本機快取，**零新增API呼叫**。

**4碼普通股過濾（佇列#55規格寫死的必要步驟）**：T86原始列含ETF/權證/
反向型商品（如`00715L`/`050257`），必須先濾成`stock_id`恰為4碼數字
（正規表示式`^[0-9]{4}$`）的普通股才能算截面統計量，否則ETF會主導截面
（跟#53/#54各自處理非個股聚合列的道理相同,但這裡的過濾規則更嚴格——
#53/#54只排除「非數字開頭」,這裡連ETF/權證的4碼以外或帶字母代碼也要排除）。
抽樣結果:2015-01-05=845檔、2018-01-02=809檔、2021-01-04=935檔、
2024-12-31=1033檔（4碼普通股數字量級跟先前查證表「988檔@2024-01-02」
接近，符合預期）。

**規模標準化分母**：沿用`turnover_concentration_gate54.py::_load_money_long()`
（`Trading_money`欄，同一批`data/raw/TaiwanStockPrice__*.parquet`快取,
零新增API呼叫），對T86與money資料各自過濾4碼後再做inner merge——merge本身
就是雙重過濾(T86端已限4碼、money端也需另外限4碼,ETF/權證在money端不會被
排除,必須在merge前主動過濾,見`_filter_4digit()`)。

**與#53/#54相關係數檢查**：雖然`HYPOTHESIS_QUEUE.md` #55條目本身未明文
要求這一步（只有#54條目要求檢查跟#53的相關係數），但`CLAUDE.md`「同家族
因子只能算一個獨立發現」是通則不是單一條目專屬規則，本輪比照辦理一併算出,
不留給下一輪。
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

T86_DIR = Path(__file__).parent / "data" / "raw_twse_t86"
MIN_STOCKS_PER_DATE = 300
VEL_WINDOW = 20
PCTILE_WARMUP = 60
FORWARD_HORIZON = 20
GATE53_CSV = Path(__file__).parent / "data" / "cross_sectional_dispersion_gate53.csv"
GATE54_CSV = Path(__file__).parent / "data" / "turnover_concentration_gate54.csv"
FOUR_DIGIT_RE = re.compile(r"^[0-9]{4}$")


def _filter_4digit(df: pd.DataFrame, col: str = "stock_id") -> pd.DataFrame:
    return df[df[col].str.match(FOUR_DIGIT_RE)]


def _load_t86_flow_long() -> pd.DataFrame:
    """回傳long-form DataFrame(columns=date, stock_id, total_net)，逐檔三大
    法人合計淨買超金額，已濾成4碼普通股。每個T86_*.parquet是單一交易日的
    全市場截面快照（非逐檔獨立檔案，跟price/#53/#54的檔案結構相反），
    逐檔讀取、單檔壞掉不拖垮整體。"""
    files = sorted(T86_DIR.glob("T86_*.parquet"))
    frames = []
    n_ok, n_err, n_empty = 0, 0, 0
    for f in files:
        try:
            df = pd.read_parquet(f, columns=["date", "stock_id", "total_net"])
        except Exception as e:  # noqa: BLE001 -- 單日檔案壞掉不拖垮整體
            print(f"  {f.name}: read ERROR ({e}), dropping")
            n_err += 1
            continue
        if df.empty:
            n_empty += 1
            continue
        df = _filter_4digit(df)
        if df.empty:
            n_empty += 1
            continue
        df["date"] = pd.to_datetime(df["date"])
        frames.append(df)
        n_ok += 1
    print(f"T86逐日檔案載入結果: ok={n_ok} err={n_err} empty(無4碼普通股列)={n_empty} 總檔案數={len(files)}")
    if not frames:
        raise RuntimeError("no valid T86 daily snapshot loaded")
    out = pd.concat(frames, ignore_index=True)
    out = out.dropna(subset=["date", "stock_id", "total_net"])
    out = out.drop_duplicates(subset=["date", "stock_id"], keep="last")
    return out


def build_flow_dispersion_series() -> pd.DataFrame:
    """回傳index=date的DataFrame，欄位flow_disp/n_t/vel/level_pctile/
    vel_pctile。全程只用截至當下(含當日)的資料。"""
    t86 = _load_t86_flow_long()
    money = _load_money_long()
    money = _filter_4digit(money)
    print(f"T86 4碼普通股列數={len(t86)}，money 4碼普通股列數={len(money)}")

    merged = t86.merge(money, on=["date", "stock_id"], how="inner")
    print(f"T86 x money inner merge後共同(date,stock_id)列數={len(merged)}")
    merged = merged[merged["money"] > 0]
    merged["f"] = merged["total_net"] / merged["money"]
    # 規模標準化後的離譜值（總量單位/成交值單位不一致的資料錯誤，或極端
    # 除權息造成的成交值瞬間萎縮）視為壞值，避免單一髒點主導std。三大
    # 法人淨買超理論上不可能超過當日成交值本身(|f|<=1)，留寬鬆邊界到5.0
    # 容許少量匯報時點差異，但排除明顯的資料錯誤（跟#53排除>500%單日
    # 報酬同一個精神）。
    n_before = len(merged)
    merged = merged[merged["f"].abs() < 5.0]
    n_extreme = n_before - len(merged)
    print(f"排除規模標準化後|f|>=5.0的離譜值: {n_extreme}/{n_before} 列（{100 * n_extreme / n_before:.2f}%）")

    grouped = merged.groupby("date")["f"].agg(flow_disp="std", n_t="count").reset_index()
    grouped = grouped.sort_values("date").reset_index(drop=True)

    n_unusable = int((grouped["n_t"] < MIN_STOCKS_PER_DATE).sum())
    print(
        f"\n總交易日數={len(grouped)}，n_t<{MIN_STOCKS_PER_DATE}的天數={n_unusable}"
        f"（{100 * n_unusable / len(grouped):.1f}%），標NaN不靜默丟棄"
    )
    grouped.loc[grouped["n_t"] < MIN_STOCKS_PER_DATE, "flow_disp"] = np.nan

    disp = grouped["flow_disp"].to_numpy()
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
    valid_disp = df["flow_disp"].dropna()
    valid_vel = df["vel"].dropna()
    stats = {
        "n_days_total": len(df),
        "n_days_valid_disp": len(valid_disp),
        "flow_disp_mean": float(valid_disp.mean()),
        "flow_disp_std": float(valid_disp.std()),
        "flow_disp_min": float(valid_disp.min()),
        "flow_disp_max": float(valid_disp.max()),
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
    non_degenerate = stats["flow_disp_std"] > 0 and stats["vel_std"] > 0 and stats["n_days_valid_vel"] > 500
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


def correlation_check_vs_prior_gates(df55: pd.DataFrame) -> dict:
    """量#55(level/vel)與#53/#54(level/vel)的相關係數，通則性檢查
    （`CLAUDE.md`「同家族因子只能算一個獨立發現」不限單一條目專屬）。
    事前約定門檻|corr|>0.7判定同家族。"""
    print("\n=== 與#53/#54訊號相關係數檢查（同家族判定，事前約定門檻|corr|>0.7） ===")
    out = {}
    for label, path in (("gate53", GATE53_CSV), ("gate54", GATE54_CSV)):
        if not path.exists():
            print(f"  {path} 不存在，跳過（{label}尚未跑過gate1）")
            out[label] = {"skipped": True, "reason": f"{path} missing"}
            continue
        other = pd.read_csv(path, parse_dates=["date"])
        merged = df55[["date", "level_pctile", "vel_pctile"]].merge(
            other[["date", "level_pctile", "vel_pctile"]], on="date", how="inner", suffixes=("_55", f"_{label[-2:]}")
        )
        merged = merged.dropna()
        corr_level = float(merged.iloc[:, 1].corr(merged.iloc[:, 3]))
        corr_vel = float(merged.iloc[:, 2].corr(merged.iloc[:, 4]))
        same_family = abs(corr_level) > 0.7 or abs(corr_vel) > 0.7
        print(f"  vs {label}: n_aligned={len(merged)} corr_level={corr_level:+.4f} corr_vel={corr_vel:+.4f} 同家族={same_family}")
        out[label] = {"n_aligned": len(merged), "corr_level": corr_level, "corr_vel": corr_vel, "same_family": bool(same_family)}
    return out


def main():
    print("=== #55 三大法人買賣超截面離散度速度 第1關 sanity ===")
    df = build_flow_dispersion_series()
    df.to_csv(Path(__file__).parent / "data" / "institutional_flow_dispersion_gate55.csv", index=False)

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
