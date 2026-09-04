"""`HYPOTHESIS_QUEUE.md` #31 台指選擇權Put/Call成交量比率當市場regime/擇時
訊號——GATE_SEQUENCE第2關以後（把第1關cheap gate已驗證的時序相關性，轉成
具體台股當日曝險擇時規則，比照`spillover_overlay_v1.py`(#19)同一個overlay
精神走完整第2~9關）。

**背景**：`option_pcr_gate.py`（上一輪）已證明台指選擇權Put/Call成交量比率
（僅日盤`position`口徑）對台股次一交易日close-to-close報酬有結構性時序
相關（TRAIN r=+0.0611 p=0.0193、VAL r=+0.0587 p=0.0676，皆同號，VAL贏過
洗牌null percentile=94.0），但那只是「相關性存在性」驗證，不是可部署策略。
這裡把訊號轉成`HYPOTHESIS_QUEUE.md` #31條目建議的具體規則。

**曝險規則（第一版，事前綁定，非搜尋/優化後選定）**：PCR本身跨10年（2015~
2024）可能有結構性水位飄移（選擇權市場成熟度/參與者組成改變），不適合用
絕對數值定門檻——改用「PCR在自身trailing窗口內的百分位排名」：
  `pcr_pctl[t] = percentile_rank(pcr[t] within pcr[t-WINDOW+1 : t])`
  `exposure[t] = EXPOSURE_DOWN if pcr_pctl[t] < THRESHOLD_PCTL else EXPOSURE_UP`
只用過去(含當天)WINDOW天的PCR算百分位排名，不用任何未來資訊。跟
`spillover_overlay_v1.py`/`regime_overlay.py`同一個「不允許槓桿、單邊防禦型」
精神：正常/訊號非低時維持1.0，只在訊號低時降曝險，THRESHOLD_PCTL=0.30、
EXPOSURE_DOWN=0.3（跟`regime_overlay.py`最差組合0.40、`spillover_overlay_v1.py`
0.3同一個量級，非優化結果）、WINDOW=250（約1年交易日）。**方向依第1關
cheap gate的實證結果決定**（PCR越高、次日台股報酬越正 —— 兩期r皆為正），
故「PCR百分位偏低」對應成本身條目所稱的防禦訊號，不是預先綁定文獻上的
逆向/順向立場，是照已驗證的相關方向設計。

**時序對齊**：沿用`option_pcr_gate.py`的`build_aligned_series()`，`tw_ret[t]`
本身就是用「signal_date（t日）收盤後才完整可得」的PCR預測的「下一個」台股
交易日報酬，`exposure[t]`可以直接套用在對應的`tw_ret[t]`上，不需要再shift，
跟#19同一個理由（時序對齊已經在資料層做掉，不是這裡才做）。

**成本模型**：曝險在1.0/0.3兩檔之間切換，每次切換視為交易`|Δexposure|`
比例的TAIEX代理部位，完全比照`spillover_overlay_v1.py`同一套
`_switch_cost_pct`/`apply_costs`實作（手續費/證交稅/滑價三項同乘同一個
倍數做1x/2x/3x敏感度），不重新發明費率假設，本檔獨立複製一份小函式（跟
本佇列#10/#19/#26/#28/#29/#30既有慣例一致：每個假設腳本自成一份可重跑
單元，不建立共用overlay模組）。

**資料重用（禮儀，不重打FinMind）**：直接讀`option_pcr_gate.py`上一輪已
產出的`data/option_pcr_aligned.csv`快取（涵蓋2015-01-05~2024-12-30全部
TRAIN+VAL範圍），不重新呼叫`build_pcr_series()`打API。

2026-09-05 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程接續執行。
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import portfolio_backtest_v2 as pbv2
from yf_price_client import fetch_yf_index
from validation import costs as costs_mod
from validation.holdout import TRAIN_END, VAL_END

WINDOW = 250
MIN_PERIODS = 60
THRESHOLD_PCTL = 0.30
EXPOSURE_DOWN = 0.3
EXPOSURE_UP = 1.0

ALIGNED_CACHE = Path(__file__).parent / "data" / "option_pcr_aligned.csv"

KNOWN_CRISIS_WINDOWS = {
    "2018Q4貿易戰急跌": ("2018-10-01", "2018-12-31"),
    "2020Q1新冠崩盤": ("2020-02-01", "2020-04-30"),
    "2022全年空頭": ("2022-01-01", "2022-12-31"),
}


# ---------------------------------------------------------------------------
# 資料載入 + 訊號 -> 曝險
# ---------------------------------------------------------------------------

def load_aligned() -> pd.DataFrame:
    if not ALIGNED_CACHE.exists():
        raise RuntimeError(f"找不到{ALIGNED_CACHE}，請先跑option_pcr_gate.py產生對齊快取")
    df = pd.read_csv(ALIGNED_CACHE, parse_dates=["signal_date", "tw_date"])
    return df.sort_values("signal_date").reset_index(drop=True)


def _rolling_pctl_rank(s: pd.Series, window: int, min_periods: int) -> pd.Series:
    """每個t的值在[t-window+1, t]窗口內(含自己)的百分位排名。只用過去(含
    當天)資料，無未來函數。"""
    return s.rolling(window=window, min_periods=min_periods).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
    )


def build_overlay(aligned: pd.DataFrame, window: int = WINDOW, min_periods: int = MIN_PERIODS,
                   threshold_pctl: float = THRESHOLD_PCTL, exposure_down: float = EXPOSURE_DOWN,
                   exposure_up: float = EXPOSURE_UP) -> pd.DataFrame:
    d = aligned.sort_values("signal_date").reset_index(drop=True).copy()
    d["pcr_pctl"] = _rolling_pctl_rank(d["pcr"], window, min_periods)
    # 歷史不足(前面min_periods天)沒有足夠窗口判斷時，預設維持基準曝險
    # (不因資料不足武斷判防禦)，是事前綁定的保守選擇。
    d["exposure"] = np.where(d["pcr_pctl"].isna(), exposure_up,
                              np.where(d["pcr_pctl"] < threshold_pctl, exposure_down, exposure_up))
    d["overlay_return_gross"] = d["tw_ret"] * d["exposure"]
    prev_exposure = d["exposure"].shift(1).fillna(exposure_up)
    d["exposure_change"] = d["exposure"] - prev_exposure
    return d.sort_values("tw_date").reset_index(drop=True)


def _switch_cost_pct(delta_exposure: float, mult: float = 1.0, slippage_bps: float = costs_mod.DEFAULT_SLIPPAGE_BPS,
                      commission_discount: float = 1.0) -> float:
    if delta_exposure == 0:
        return 0.0
    notional = abs(delta_exposure)
    fee = notional * costs_mod.COMMISSION_RATE * commission_discount * mult
    slip = notional * (slippage_bps / 10_000) * mult
    if delta_exposure < 0:
        tax = notional * costs_mod.SECURITIES_TX_TAX_NORMAL * mult
        return fee + slip + tax
    return fee + slip


def apply_costs(d: pd.DataFrame, mult: float = 1.0) -> pd.DataFrame:
    out = d.copy()
    out["cost_pct"] = out["exposure_change"].apply(lambda dc: _switch_cost_pct(dc, mult=mult))
    out["overlay_return_net"] = out["overlay_return_gross"] - out["cost_pct"]
    out["baseline_equity"] = (1 + out["tw_ret"]).cumprod()
    out["overlay_equity_net"] = (1 + out["overlay_return_net"]).cumprod()
    return out


def _split(d: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = d[d["tw_date"] <= pd.Timestamp(TRAIN_END)].reset_index(drop=True)
    val = d[(d["tw_date"] > pd.Timestamp(TRAIN_END)) & (d["tw_date"] <= pd.Timestamp(VAL_END))].reset_index(drop=True)
    return train, val


def _metrics(ret: pd.Series) -> dict:
    ret = ret.dropna()
    if len(ret) < 30 or ret.std() == 0:
        return {"total_return_pct": float("nan"), "cagr_pct": float("nan"), "sharpe": float("nan"),
                "mdd_pct": float("nan"), "n_days": len(ret)}
    equity = (1 + ret).cumprod()
    total_return = float(equity.iloc[-1] - 1)
    years = len(ret) / 252.0
    cagr = float(equity.iloc[-1] ** (1 / years) - 1)
    sharpe = float(ret.mean() / ret.std() * np.sqrt(252))
    running_max = equity.cummax()
    mdd = float((equity / running_max - 1).min())
    return {"total_return_pct": total_return * 100, "cagr_pct": cagr * 100, "sharpe": sharpe,
            "mdd_pct": mdd * 100, "n_days": len(ret)}


# ---------------------------------------------------------------------------
# 第2關：隨機控制組（打亂exposure時序，N=100）
# ---------------------------------------------------------------------------

def gate2_random_control(d: pd.DataFrame, label: str, n_draws: int = 100, seed: int = 20260905) -> dict:
    rng = np.random.default_rng(seed)
    exposure_vals = d["exposure"].to_numpy()
    raw_ret = d["tw_ret"].to_numpy()
    real_net = d["overlay_return_net"].dropna()
    real_sharpe = float(real_net.mean() / real_net.std() * np.sqrt(252)) if real_net.std() > 0 else float("nan")
    real_equity = (1 + real_net).cumprod()
    real_total = float(real_equity.iloc[-1] - 1) if len(real_equity) else float("nan")

    sharpes, totals = [], []
    for _ in range(n_draws):
        perm = rng.permutation(exposure_vals)
        sim_gross = raw_ret * perm
        sim_change = pd.Series(perm).diff().fillna(perm[0] - EXPOSURE_UP).to_numpy()
        sim_cost = np.array([_switch_cost_pct(dc) for dc in sim_change])
        sim_net = pd.Series(sim_gross - sim_cost).dropna()
        if sim_net.std() == 0 or len(sim_net) < 30:
            continue
        sharpes.append(float(sim_net.mean() / sim_net.std() * np.sqrt(252)))
        totals.append(float((1 + sim_net).cumprod().iloc[-1] - 1))

    sharpe_pctl = 100.0 * float(np.mean(np.array(sharpes) <= real_sharpe))
    total_pctl = 100.0 * float(np.mean(np.array(totals) <= real_total))
    print(f"\n--- 第2關隨機控制組 {label}（打亂exposure時序，N={len(sharpes)}draws）---")
    print(f"  真實(1x成本)Sharpe={real_sharpe:.3f}  打亂分布median={np.median(sharpes):.3f}  percentile={sharpe_pctl:.1f}")
    print(f"  真實(1x成本)總報酬={real_total*100:+.2f}%  打亂分布median={np.median(totals)*100:+.2f}%  percentile={total_pctl:.1f}")
    return {"label": label, "real_sharpe": real_sharpe, "sharpe_percentile": sharpe_pctl,
            "real_total_return_pct": real_total * 100, "total_return_percentile": total_pctl,
            "n_draws": len(sharpes)}


# ---------------------------------------------------------------------------
# 第3關：參數密集高原（TRAIN期only，1x成本）
# ---------------------------------------------------------------------------

def gate3_parameter_plateau(aligned_train_raw: pd.DataFrame) -> dict:
    print("\n" + "=" * 70)
    print("第3關：參數密集高原（TRAIN期，1x成本）")
    print("=" * 70)
    threshold_grid = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
    exposure_down_grid = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    rows = []
    for th in threshold_grid:
        for ed in exposure_down_grid:
            d = build_overlay(aligned_train_raw, threshold_pctl=th, exposure_down=ed)
            d = apply_costs(d, mult=1.0)
            m = _metrics(d["overlay_return_net"])
            rows.append({"threshold_pctl": th, "exposure_down": ed, "total_return_pct": m["total_return_pct"]})
    grid_df = pd.DataFrame(rows)
    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    grid_df.to_csv(out_dir / "option_pcr_overlay_gate3_grid.csv", index=False)

    n_positive = int((grid_df["total_return_pct"] > 0).sum())
    frac_positive = n_positive / len(grid_df)
    anchor_row = grid_df[(grid_df["threshold_pctl"] == THRESHOLD_PCTL) & (grid_df["exposure_down"] == EXPOSURE_DOWN)]
    anchor_return = float(anchor_row["total_return_pct"].iloc[0]) if len(anchor_row) else float("nan")
    print(f"  登錄門檻點(threshold_pctl={THRESHOLD_PCTL},exposure_down={EXPOSURE_DOWN})報酬={anchor_return:+.2f}%；"
          f"網格{len(grid_df)}點中報酬為正的有{n_positive}點({frac_positive*100:.0f}%)")
    gate3_pass = frac_positive >= 0.60
    print(f"  第3關判定（門檻：網格內>=60%的點報酬為正，非孤峰）：{'PASS' if gate3_pass else 'FAIL'}")
    return {"pass": gate3_pass, "frac_positive": frac_positive, "anchor_return_pct": anchor_return,
            "grid": grid_df.to_dict("records")}


# ---------------------------------------------------------------------------
# 第5關：leave-one-out（TRAIN期逐年拿掉最大貢獻年份）
# ---------------------------------------------------------------------------

def gate5_leave_one_out(train_net: pd.DataFrame) -> dict:
    print("\n" + "=" * 70)
    print("第5關：leave-one-out（TRAIN期逐年拿掉最大貢獻年份）")
    print("=" * 70)
    d = train_net.copy()
    d["year"] = d["tw_date"].dt.year
    yearly = {}
    for y, g in d.groupby("year"):
        r = g["overlay_return_net"].dropna()
        if len(r) < 5:
            continue
        yearly[int(y)] = float((1 + r).prod() - 1)
    print(f"  逐年報酬：{ {y: f'{v*100:+.2f}%' for y, v in yearly.items()} }")

    compounded_total = 1.0
    for v in yearly.values():
        compounded_total *= (1 + v)
    compounded_total_pct = (compounded_total - 1) * 100
    print(f"  逐年複利連乘總報酬={compounded_total_pct:+.2f}%")

    if not yearly:
        return {"pass": False, "yearly": yearly, "compounded_total_pct": compounded_total_pct}

    max_year = max(yearly, key=lambda y: yearly[y])
    loo_compounded = 1.0
    for y, v in yearly.items():
        if y == max_year:
            continue
        loo_compounded *= (1 + v)
    loo_total_pct = (loo_compounded - 1) * 100
    print(f"  貢獻最大年份={max_year}（{yearly[max_year]*100:+.2f}%）；拿掉後剩餘複利總報酬={loo_total_pct:+.2f}%")

    gate5_pass = not (compounded_total_pct > 0 and loo_total_pct <= 0)
    print(f"  第5關判定（門檻：原本為正的話，拿掉最大貢獻年份後不能翻負）：{'PASS' if gate5_pass else 'FAIL'}")
    return {"pass": gate5_pass, "yearly": yearly, "compounded_total_pct": compounded_total_pct,
            "max_year": max_year, "loo_total_pct": loo_total_pct}


# ---------------------------------------------------------------------------
# 第6關：逐年一致性（TRAIN期各年度獨立判方向）
# ---------------------------------------------------------------------------

def gate6_yearly_consistency(train_net: pd.DataFrame) -> dict:
    print("\n" + "=" * 70)
    print("第6關：逐年一致性（TRAIN期各年度獨立判方向，門檻>=5/6正）")
    print("=" * 70)
    d = train_net.copy()
    d["year"] = d["tw_date"].dt.year
    rows = []
    for y, g in d.groupby("year"):
        r = g["overlay_return_net"].dropna()
        if len(r) < 5:
            continue
        ret_pct = float((1 + r).prod() - 1) * 100
        rows.append({"year": int(y), "return_pct": ret_pct, "n_days": len(r)})
        print(f"    {int(y)}: 報酬={ret_pct:+8.2f}%  n_days={len(r)}")
    yearly_df = pd.DataFrame(rows)
    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    yearly_df.to_csv(out_dir / "option_pcr_overlay_gate6_yearly.csv", index=False)

    n_positive = int((yearly_df["return_pct"] > 0).sum())
    n_years = len(yearly_df)
    gate6_pass = (n_years >= 5) and (n_positive >= 5) if n_years >= 6 else (n_positive >= max(1, n_years - 1))
    print(f"\n  {n_years}個年度中報酬為正的有{n_positive}個")
    print(f"  第6關判定（門檻：>=6個年度時要求>=5/6正；不足6年時退化為寬鬆檢查，見結果標註）："
          f"{'PASS' if gate6_pass else 'FAIL'}")
    return {"pass": gate6_pass, "n_positive": n_positive, "n_years": n_years,
            "yearly": yearly_df.to_dict("records"), "full_gate_years": n_years >= 6}


# ---------------------------------------------------------------------------
# 第4關：成本敏感度 / 第8關：alpha顯著性拆解 / 第9關：下檔保護
# ---------------------------------------------------------------------------

def gate4_cost_sensitivity(d_train: pd.DataFrame, d_val: pd.DataFrame) -> dict:
    print("\n" + "=" * 70)
    print("第4關：成本敏感度（1x/2x/3x）")
    print("=" * 70)
    out = {}
    for label, base in (("TRAIN", d_train), ("VAL", d_val)):
        row = {}
        for mult in (1, 2, 3):
            dd = apply_costs(build_overlay(base), mult=float(mult))
            m = _metrics(dd["overlay_return_net"])
            row[f"cost_{mult}x_pct"] = m["total_return_pct"]
        out[label] = row
        print(f"  {label}: 1x={row['cost_1x_pct']:+.2f}%  2x={row['cost_2x_pct']:+.2f}%  3x={row['cost_3x_pct']:+.2f}%")
    return out


def gate8_alpha_decomposition(d_train: pd.DataFrame, d_val: pd.DataFrame,
                               tw_close_train: pd.DataFrame, tw_close_val: pd.DataFrame) -> dict:
    print("\n" + "=" * 70)
    print("第8關：alpha顯著性 + beta拆解（本專案既定標準，非腳本內建percentile判準）")
    print("=" * 70)
    out = {}
    for label, d, mkt in (("TRAIN", d_train, tw_close_train), ("VAL", d_val, tw_close_val)):
        equity_curve = pd.DataFrame({"date": d["tw_date"], "equity": d["overlay_equity_net"]})
        alpha = pbv2.alpha_significance(equity_curve, mkt)
        out[label] = alpha
        print(f"  {label}: alpha(年化)={alpha['alpha_ann_pct']:+.2f}%  beta={alpha['beta']:+.3f}  "
              f"p={alpha['alpha_pvalue']:.4f}  顯著為正={alpha['alpha_significant']}")
    return out


def gate9_downside_protection(d_train: pd.DataFrame, d_val: pd.DataFrame) -> dict:
    print("\n" + "=" * 70)
    print("第9關：下檔保護證明（MDD對照 + 已知危機期間 + 大跌日尾部）")
    print("=" * 70)
    out = {}
    for label, d in (("TRAIN", d_train), ("VAL", d_val)):
        base_ret = d["tw_ret"].dropna()
        over_ret = d["overlay_return_net"].dropna()
        base_m = _metrics(base_ret)
        over_m = _metrics(over_ret)
        base_tail = float((base_ret < -0.03).mean()) * 100
        d_align = d.dropna(subset=["overlay_return_net"])
        over_tail = float((d_align["overlay_return_net"] < -0.03).mean()) * 100
        print(f"  {label}: baseline MDD={base_m['mdd_pct']:.2f}%  overlay MDD={over_m['mdd_pct']:.2f}%  "
              f"（{'改善' if over_m['mdd_pct'] > base_m['mdd_pct'] else '未改善'}）")
        print(f"         baseline單日跌幅<-3%天數占比={base_tail:.2f}%  overlay={over_tail:.2f}%  "
              f"（{'改善' if over_tail < base_tail else '未改善'}）")
        out[label] = {"baseline_mdd_pct": base_m["mdd_pct"], "overlay_mdd_pct": over_m["mdd_pct"],
                       "mdd_improved": over_m["mdd_pct"] > base_m["mdd_pct"],
                       "baseline_tail_pct": base_tail, "overlay_tail_pct": over_tail,
                       "tail_improved": over_tail < base_tail}

    print("\n  --- 已知危機期間 曝險/MDD 檢查 ---")
    full = pd.concat([d_train, d_val], ignore_index=True)
    crisis_rows = {}
    for name, (start, end) in KNOWN_CRISIS_WINDOWS.items():
        window = full[(full["tw_date"] >= start) & (full["tw_date"] <= end)]
        if window.empty:
            print(f"  {name}: 該期間資料為0筆，跳過")
            continue
        avg_exposure = float(window["exposure"].mean())
        base_win_m = _metrics(window["tw_ret"].dropna())
        over_win_m = _metrics(window["overlay_return_net"].dropna())
        print(f"  {name} ({start}~{end}, n={len(window)}): 平均曝險={avg_exposure:.2f}  "
              f"窗內baseline MDD={base_win_m['mdd_pct']:.2f}%  窗內overlay MDD={over_win_m['mdd_pct']:.2f}%")
        crisis_rows[name] = {"avg_exposure": avg_exposure, "baseline_mdd_pct": base_win_m["mdd_pct"],
                              "overlay_mdd_pct": over_win_m["mdd_pct"]}
    out["crisis_windows"] = crisis_rows
    return out


def main() -> dict:
    t0 = time.time()
    print("載入台股選擇權PCR對齊資料（重用option_pcr_gate.py既有快取，不重打API）...")
    aligned = load_aligned()
    tw_close = fetch_yf_index(ticker="^TWII", start_date="2010-01-01")[["date", "close"]].copy()
    tw_close["date"] = pd.to_datetime(tw_close["date"])

    aligned_train_raw, aligned_val_raw = _split(aligned)
    tw_close_train = tw_close[tw_close["date"] <= pd.Timestamp(TRAIN_END)].reset_index(drop=True)
    tw_close_val = tw_close[(tw_close["date"] > pd.Timestamp(TRAIN_END)) & (tw_close["date"] <= pd.Timestamp(VAL_END))].reset_index(drop=True)
    print(f"  TRAIN(<= {TRAIN_END}): n={len(aligned_train_raw)}  VAL({TRAIN_END}~{VAL_END}): n={len(aligned_val_raw)}")

    d_train = apply_costs(build_overlay(aligned_train_raw), mult=1.0)
    d_val = apply_costs(build_overlay(aligned_val_raw), mult=1.0)

    print(f"\n錨點參數：WINDOW={WINDOW}  THRESHOLD_PCTL={THRESHOLD_PCTL}  EXPOSURE_DOWN={EXPOSURE_DOWN}  EXPOSURE_UP={EXPOSURE_UP}")
    print(f"  TRAIN期防禦曝險天數占比={float((d_train['exposure']<EXPOSURE_UP).mean())*100:.1f}%  "
          f"VAL期={float((d_val['exposure']<EXPOSURE_UP).mean())*100:.1f}%")
    train_m = _metrics(d_train["overlay_return_net"])
    val_m = _metrics(d_val["overlay_return_net"])
    train_base_m = _metrics(d_train["tw_ret"])
    val_base_m = _metrics(d_val["tw_ret"])
    print(f"  TRAIN: overlay報酬={train_m['total_return_pct']:+.2f}%  baseline(買進持有)={train_base_m['total_return_pct']:+.2f}%")
    print(f"  VAL:   overlay報酬={val_m['total_return_pct']:+.2f}%  baseline(買進持有)={val_base_m['total_return_pct']:+.2f}%")

    gate2_train = gate2_random_control(d_train, "TRAIN")
    gate2_val = gate2_random_control(d_val, "VAL")

    gate3 = gate3_parameter_plateau(aligned_train_raw)
    if not gate3["pass"]:
        result = {"final_gate": 3, "verdict": "FAIL", "gate2_train": gate2_train, "gate2_val": gate2_val, "gate3": gate3}
        print(f"\n**第3關參數高原未過，快殺判定FAIL，不進第5關以後。**（耗時{time.time()-t0:.1f}s）")
        return result

    gate5 = gate5_leave_one_out(d_train)
    if not gate5["pass"]:
        result = {"final_gate": 5, "verdict": "FAIL", "gate2_train": gate2_train, "gate2_val": gate2_val,
                   "gate3": gate3, "gate5": gate5}
        print(f"\n**第5關leave-one-out未過，快殺判定FAIL，不進第6關以後。**（耗時{time.time()-t0:.1f}s）")
        return result

    gate6 = gate6_yearly_consistency(d_train)
    if not gate6["pass"]:
        result = {"final_gate": 6, "verdict": "FAIL", "gate2_train": gate2_train, "gate2_val": gate2_val,
                   "gate3": gate3, "gate5": gate5, "gate6": gate6}
        print(f"\n**第6關逐年一致性未過，快殺判定FAIL，不進第7關以後。**（耗時{time.time()-t0:.1f}s）")
        return result

    gate4 = gate4_cost_sensitivity(aligned_train_raw, aligned_val_raw)
    gate8 = gate8_alpha_decomposition(d_train, d_val, tw_close_train, tw_close_val)
    gate9 = gate9_downside_protection(d_train, d_val)

    val_alpha_significant = bool(gate8["VAL"]["alpha_significant"])
    val_downside_ok = bool(gate9["VAL"]["mdd_improved"])
    verdict = "PASS" if (val_alpha_significant and val_downside_ok) else "FAIL"

    print("\n" + "=" * 70)
    print(f"最終判定：{verdict}")
    print(f"  VAL alpha顯著為正: {val_alpha_significant} (p={gate8['VAL']['alpha_pvalue']:.4f})")
    print(f"  VAL下檔保護(MDD改善): {val_downside_ok}")
    print("=" * 70)

    result = {"final_gate": 9, "verdict": verdict, "gate2_train": gate2_train, "gate2_val": gate2_val,
              "gate3": gate3, "gate4": gate4, "gate5": gate5, "gate6": gate6, "gate8": gate8, "gate9": gate9,
              "train_metrics": train_m, "val_metrics": val_m,
              "train_baseline_metrics": train_base_m, "val_baseline_metrics": val_base_m}
    print(f"\n(耗時{time.time()-t0:.1f}s)")
    return result


if __name__ == "__main__":
    main()
