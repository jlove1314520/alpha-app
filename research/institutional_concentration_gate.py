"""`HYPOTHESIS_QUEUE.md` #43 三大法人買賣超集中度（Institutional Buying
Concentration）當市場領漲廣度regime訊號 第1關cheap gate（2026-09-06）。

經濟理由：市場技術分析文獻長期記錄過「多頭末端常伴隨領漲股窄化」
（narrow leadership，資金集中湧入少數幾檔權值/熱門股，而非廣泛分散
買進）這個市場內部結構脆弱化的警訊；資金廣泛分散買進多檔個股通常對應
更健康的多頭延續。跟本佇列前42條已死的regime/籌碼類假設在資料建構
維度上皆不同（不是單一外部序列水位/成長率、不是個股自身時間序列
持續性、不是個股間報酬相關結構、不是散戶槓桿），這條看的是**三大法人
（外資+投信+自營商合計）每日買賣超金額，在整個股票宇宙橫斷面上的
分布集中度**。完整經濟理由/已知相關背景/資料可行性見`HYPOTHESIS_QUEUE.md`
#43條目。

**訊號定義**：對既有300檔快取宇宙（跟`avg_pairwise_correlation_gate.py`
同一個seed/樣本數，複用同一批`adjusted_price_series`快取），逐日計算
每檔股票三大法人買賣超金額 = `total_net`（股數，來自`factors.py`
`_institutional_daily_net()`，T86為主/FinMind補缺口的hybrid）× 當日
收盤價。逐日橫斷面計算兩個候選集中度指標（只對當日買賣超金額為正的
個股計算，代表「買超參與廣度」，賣超不計入分母，因為假設關注的是資金
湧入的集中/分散，不是賣壓）：
  1. HHI：各檔正買超金額佔當日全體正買超總金額比重的平方和。
  2. Top10比例：當日買超金額最大的10檔佔全體正買超總金額比例。
用trailing 20個交易日移動平均平滑單日雜訊，再取該平滑值相對自身
trailing 60個交易日（含當日）的百分位排名（0~1，越高代表越異常偏高）
當regime訊號，跟`day_trading_ratio_gate.py`/`avg_pairwise_correlation_gate.py`
同一套「原始值→trailing百分位」轉換方式。

**兩個候選指標的取捨（事前用穩定度決定，不用相關性結果挑，避免多重
比較/事後選擇偏誤）**：先只看TRAIN期原始訊號（尚未接觸目標變數/相關性
檢定）的資料工程穩定度——當日有效樣本數（多少個交易日有>=
`MIN_POSITIVE_STOCKS`檔正買超個股可以算集中度）與變異係數，選穩定度
較高者當主要訊號，另一個僅供對照報告，不用來判定CHEAP_PASS/FAIL。

**目標變數**：訊號日之後（不含當日）N=20個交易日TAIEX累積報酬。

**時序對齊**：訊號用t日盤後才完整可得的三大法人買賣超與收盤價資料，
預測t日之後的未來窗口，不解釋t日當天，無未來函數。

**事前綁定方向**：負（`HYPOTHESIS_QUEUE.md` #43「集中度百分位偏高→
預期未來報酬轉差」）。

**判定標準（跟本佇列既有cheap gate三項判準同一套框架，比照
`day_trading_ratio_gate.py`/`avg_pairwise_correlation_gate.py`）**：
TRAIN=[universe起點, TRAIN_END]、VAL=(TRAIN_END, VAL_END]（既有
`validation/holdout.py`邊界），Spearman相關係數，N=200次時序洗牌null
（打散訊號時序、保留TAIEX報酬時序）。

2026-09-06由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，本輪從第1關
cheap gate開始，不跳關。零新資料源——三大法人日頻買賣超資料複用
`#13`/`#41`已驗證可行的T86快取路徑，價格資料複用`avg_pairwise_correlation_gate.py`
已驗證可行的300檔快取宇宙。
"""
from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from adjust import adjusted_price_series
from factors import _institutional_daily_net
from universe import universe as build_universe
from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END

SMOOTH_WINDOW = 20  # 移動平均平滑單日雜訊
PCTILE_WINDOW = 60  # 相對自身trailing歷史的百分位排名窗口
FORWARD_HORIZON = 20
N_SHUFFLE = 200
SHUFFLE_SEED = 20260906
MIN_ABS_CORR = 0.02
EXPECTED_SIGN = -1  # 事前綁定：集中度異常偏高 -> 未來報酬應偏差（負相關）
SAMPLE_SIZE = 300
SAMPLE_SEED = 20260822  # 跟avg_pairwise_correlation_gate.py同一批300檔宇宙
START_DATE = "2010-01-01"
MIN_STOCKS_VALID = 30  # 當日至少要有這麼多檔股票有有效net_amount資料才計算集中度
MIN_POSITIVE_STOCKS = 10  # 且其中至少這麼多檔淨買超為正才計算集中度（避免稀疏日雜訊）


def _sample_universe_ids() -> list[str]:
    uni = build_universe()
    ids = sorted(uni["stock_id"].unique().tolist())
    rng = random.Random(SAMPLE_SEED)
    rng.shuffle(ids)
    return ids[:SAMPLE_SIZE]


def _load_net_amount_panel(stock_ids: list[str]) -> pd.DataFrame:
    """回傳long格式 DataFrame(date, stock_id, net_amount)，
    net_amount = 三大法人合計買賣超股數 * 當日收盤價。"""
    frames = []
    for i, sid in enumerate(stock_ids):
        try:
            px = adjusted_price_series(sid, START_DATE)
        except Exception as e:  # noqa: BLE001 -- 跟factor_ic.py/avg_pairwise同一套容錯
            print(f"  [{i + 1}/{len(stock_ids)}] {sid}: price ERROR ({e}), dropping")
            continue
        if px.empty:
            continue
        try:
            inst = _institutional_daily_net(sid, START_DATE)
        except Exception as e:  # noqa: BLE001 -- 三大法人資料失敗不能讓整批中斷
            print(f"  [{i + 1}/{len(stock_ids)}] {sid}: institutional ERROR ({e}), dropping")
            continue
        if inst.empty:
            continue
        px_small = px[["date", "close"]].copy()
        px_small["date"] = pd.to_datetime(px_small["date"])
        inst_small = inst[["date", "total_net"]].copy()
        inst_small["date"] = pd.to_datetime(inst_small["date"])
        merged = pd.merge(px_small, inst_small, on="date", how="inner")
        if merged.empty:
            continue
        merged["net_amount"] = merged["total_net"] * merged["close"]
        merged["stock_id"] = sid
        frames.append(merged[["date", "stock_id", "net_amount"]])
        if (i + 1) % 50 == 0:
            print(f"  已處理 {i + 1}/{len(stock_ids)} 檔...")
    if not frames:
        raise RuntimeError("no valid stock net_amount series loaded")
    return pd.concat(frames, ignore_index=True)


def _daily_concentration(panel: pd.DataFrame) -> pd.DataFrame:
    """逐日計算HHI與Top10比例兩個候選集中度指標。"""
    rows = []
    for date, g in panel.groupby("date"):
        vals = g["net_amount"].to_numpy()
        n_valid = int(np.sum(~np.isnan(vals)))
        if n_valid < MIN_STOCKS_VALID:
            continue
        pos = vals[vals > 0]
        n_pos = len(pos)
        if n_pos < MIN_POSITIVE_STOCKS:
            continue
        total_pos = pos.sum()
        shares = pos / total_pos
        hhi = float(np.sum(shares**2))
        top10 = float(np.sort(pos)[::-1][:10].sum() / total_pos)
        rows.append({"date": date, "n_valid": n_valid, "n_pos": n_pos, "hhi": hhi, "top10": top10})
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def _rolling_percentile_rank(values: np.ndarray, window: int) -> np.ndarray:
    """對每個位置i（i>=window-1），回傳values[i]在values[i-window+1:i+1]
    這個窗口內的百分位排名（0~1，1=窗口內最大值）。窗口不足回傳NaN。"""
    n = len(values)
    out = np.full(n, np.nan)
    for i in range(window - 1, n):
        w = values[i - window + 1 : i + 1]
        out[i] = float((w <= values[i]).sum() - 1) / (window - 1)
    return out


def _build_signal_for_metric(conc: pd.DataFrame, metric: str) -> pd.Series:
    smoothed = conc[metric].rolling(SMOOTH_WINDOW, min_periods=SMOOTH_WINDOW).mean()
    pctile = _rolling_percentile_rank(smoothed.to_numpy(), PCTILE_WINDOW)
    return pd.Series(pctile, index=conc.index, name=f"{metric}_pctile")


def choose_primary_metric(conc: pd.DataFrame) -> tuple[str, dict]:
    """事前用TRAIN期原始訊號的資料工程穩定度決定主要指標，不看跟目標變數的
    相關性（避免事後挑選偏誤）。穩定度＝有效樣本數多、原始值變異係數低。"""
    train_mask = conc["date"] <= pd.Timestamp(TRAIN_END)
    train = conc[train_mask]
    stats = {}
    for metric in ("hhi", "top10"):
        vals = train[metric].dropna()
        cv = float(vals.std() / vals.mean()) if len(vals) > 0 and vals.mean() != 0 else float("inf")
        stats[metric] = {"n_days": int(len(vals)), "mean": float(vals.mean()), "std": float(vals.std()), "cv": cv}
    print("\n=== 事前指標穩定度比較（TRAIN期原始值，未接觸目標變數） ===")
    for metric, s in stats.items():
        print(f"  {metric}: n_days={s['n_days']} mean={s['mean']:.4f} std={s['std']:.4f} cv={s['cv']:.4f}")
    # 判準：有效交易日數更多者優先（代表`MIN_POSITIVE_STOCKS`門檻下更少被丟棄）；
    # 打平則變異係數更低者優先（訊號更平滑，較不受單日極端值主導）。
    primary = max(
        stats.keys(),
        key=lambda m: (stats[m]["n_days"], -stats[m]["cv"]),
    )
    print(f"  -> 選定主要指標: {primary}")
    return primary, stats


def build_aligned_series(conc: pd.DataFrame, metric: str) -> pd.DataFrame:
    sig_pctile = _build_signal_for_metric(conc, metric)
    sig = conc[["date"]].copy()
    sig["conc_raw"] = conc[metric]
    sig["conc_pctile"] = sig_pctile.to_numpy()
    sig = sig.dropna(subset=["conc_pctile"]).reset_index(drop=True)

    taiex = fetch_yf_index(ticker="^TWII", start_date=START_DATE)
    taiex = taiex.dropna(subset=["close"]).copy()
    taiex["date"] = pd.to_datetime(taiex["date"])
    taiex = taiex.sort_values("date").reset_index(drop=True)
    tw_dates = taiex["date"].to_numpy()
    tw_close = taiex["close"].to_numpy()

    rows = []
    for _, r in sig.iterrows():
        sig_date = np.datetime64(r["date"])
        start_idx = int(np.searchsorted(tw_dates, sig_date, side="right"))
        end_idx = start_idx + FORWARD_HORIZON - 1
        if end_idx >= len(tw_dates):
            continue
        fwd_ret = tw_close[end_idx] / tw_close[start_idx] - 1.0
        rows.append(
            {
                "date": r["date"],
                "conc_raw": float(r["conc_raw"]),
                "conc_pctile": float(r["conc_pctile"]),
                "fwd_ret": float(fwd_ret),
            }
        )
    return pd.DataFrame(rows)


def _split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[df["date"] <= pd.Timestamp(TRAIN_END)].copy()
    val = df[(df["date"] > pd.Timestamp(TRAIN_END)) & (df["date"] <= pd.Timestamp(VAL_END))].copy()
    return train, val


def _shuffle_percentile(signal: np.ndarray, target: np.ndarray, n: int, seed: int) -> dict:
    real_corr, real_p = spearmanr(signal, target)
    rng = np.random.default_rng(seed)
    shuffled = np.empty(n)
    for i in range(n):
        perm = rng.permutation(signal)
        shuffled[i], _ = spearmanr(perm, target)
    # 單邊檢定：事前綁定方向為負，看真實corr有多小（比洗牌null更負的比例）
    pctl = 100.0 * float(np.mean(shuffled >= real_corr))
    return {
        "real_corr": float(real_corr),
        "real_p": float(real_p),
        "null_median": float(np.median(shuffled)),
        "percentile": pctl,
    }


def evaluate(df: pd.DataFrame, label: str) -> dict:
    signal = df["conc_pctile"].to_numpy()
    target = df["fwd_ret"].to_numpy()
    n = len(df)
    shuf = _shuffle_percentile(signal, target, N_SHUFFLE, SHUFFLE_SEED)
    print(f"\n--- {label} (n={n}) ---")
    print(f"  Spearman(conc_pctile, fwd_ret_{FORWARD_HORIZON}d) = {shuf['real_corr']:+.4f} (p={shuf['real_p']:.4f})")
    print(
        f"  洗牌null(N={N_SHUFFLE}): median={shuf['null_median']:+.4f}  "
        f"真實corr percentile(單邊，越低代表越顯著負相關)={shuf['percentile']:.1f}"
    )
    return {
        "label": label,
        "n": n,
        "corr": shuf["real_corr"],
        "p": shuf["real_p"],
        "null_median": shuf["null_median"],
        "null_percentile": shuf["percentile"],
    }


def main():
    print("=== #43 三大法人買賣超集中度 regime 訊號 第1關cheap gate ===")
    print(f"抽樣{SAMPLE_SIZE}檔股票（seed={SAMPLE_SEED}，跟avg_pairwise_correlation_gate.py同一批宇宙）...")
    stock_ids = _sample_universe_ids()
    print("載入三大法人買賣超金額（複用既有價格+T86快取）...")
    panel = _load_net_amount_panel(stock_ids)
    print(f"panel: {len(panel)}筆(股票x日期)，覆蓋{panel['stock_id'].nunique()}檔股票")

    conc = _daily_concentration(panel)
    print(f"逐日集中度指標: {len(conc)}個有效交易日（門檻：>= {MIN_STOCKS_VALID}檔有效資料 且 >= {MIN_POSITIVE_STOCKS}檔正買超）")
    if len(conc) < 60:
        print("\n樣本數過少（<60），資料可能不完整，判定FAIL（結構性資料不足）")
        return {"verdict": "FAIL", "reason": "insufficient_sample", "n": len(conc)}

    primary_metric, stability_stats = choose_primary_metric(conc)

    results_by_metric = {}
    for metric in ("hhi", "top10"):
        aligned = build_aligned_series(conc, metric)
        if aligned.empty:
            print(f"\n[{metric}] 無有效對齊資料，跳過")
            results_by_metric[metric] = {"verdict": "FAIL", "reason": "no_aligned_data"}
            continue
        train, val = _split(aligned)
        print(f"\n### 指標: {metric} ({'主要' if metric == primary_metric else '對照'}) ###")
        print(f"對齊後總配對數: {len(aligned)}  訊號日範圍: {aligned['date'].min()} ~ {aligned['date'].max()}")
        print(
            f"原始值描述統計: mean={aligned['conc_raw'].mean():.4f} median={aligned['conc_raw'].median():.4f} "
            f"std={aligned['conc_raw'].std():.4f} min={aligned['conc_raw'].min():.4f} max={aligned['conc_raw'].max():.4f}"
        )
        print(f"TRAIN(<= {TRAIN_END}): n={len(train)}  VAL({TRAIN_END}~{VAL_END}): n={len(val)}")

        if len(train) < 30 or len(val) < 30:
            print("樣本數過少（<30任一期），判定FAIL（結構性資料不足）")
            results_by_metric[metric] = {
                "verdict": "FAIL",
                "reason": "insufficient_sample_split",
                "train_n": len(train),
                "val_n": len(val),
            }
            continue

        train_result = evaluate(train, f"{metric} TRAIN (<= {TRAIN_END})")
        val_result = evaluate(val, f"{metric} VAL ({TRAIN_END} ~ {VAL_END})")

        train_sign_ok = (train_result["corr"] < 0) == (EXPECTED_SIGN < 0)
        val_sign_ok = (val_result["corr"] < 0) == (EXPECTED_SIGN < 0)
        same_sign_as_expected = train_sign_ok and val_sign_ok
        nontrivial = abs(train_result["corr"]) > MIN_ABS_CORR and abs(val_result["corr"]) > MIN_ABS_CORR
        beats_null = val_result["null_percentile"] <= 10.0

        print(f"\n  === {metric} 第1關cheap gate三項判準 ===")
        print(f"    1. 幅度非零 (|corr|>{MIN_ABS_CORR}兩期): {nontrivial}")
        print(
            f"    2. train/val皆符合事前綁定負相關方向: {same_sign_as_expected} "
            f"(TRAIN corr={train_result['corr']:+.4f}, VAL corr={val_result['corr']:+.4f})"
        )
        print(
            f"    3. VAL贏過洗牌null(單邊percentile<=10.0): {beats_null} "
            f"(percentile={val_result['null_percentile']:.1f})"
        )

        metric_verdict = "CHEAP_PASS" if (nontrivial and same_sign_as_expected and beats_null) else "FAIL"
        print(f"  [{metric}] 判定: {metric_verdict}")

        aligned.to_csv(Path(__file__).parent / "data" / f"institutional_concentration_{metric}_aligned.csv", index=False)
        results_by_metric[metric] = {
            "train": train_result,
            "val": val_result,
            "verdict": metric_verdict,
            "n_total": len(aligned),
            "train_n": len(train),
            "val_n": len(val),
        }

    final_verdict = results_by_metric.get(primary_metric, {}).get("verdict", "FAIL")
    print(f"\n=== 最終判定（依主要指標 {primary_metric}）: {final_verdict} ===")
    print("（另一指標僅供對照，不參與判定，避免事後挑選偏誤）")

    return {
        "primary_metric": primary_metric,
        "stability_stats": stability_stats,
        "results_by_metric": results_by_metric,
        "verdict": final_verdict,
    }


if __name__ == "__main__":
    main()
