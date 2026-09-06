"""`HYPOTHESIS_QUEUE.md` #48 董監事及大股東股權質押比例（Controlling
Shareholder / Insider Share Pledge Ratio）當公司治理／代理成本風險訊號
第1關cheap gate（2026-09-06 hypothesis_queue排程接續）。

**經濟理由/已知混淆風險/資料可行性查證**完整內容見`HYPOTHESIS_QUEUE.md`
#48條目，這裡只放實作重點。

**訊號定義**：對既有300檔快取宇宙（跟`avg_pairwise_correlation_gate.py`/
`institutional_concentration_gate.py`同一批`seed=20260822`樣本，取這批
樣本中同時存在於`irb130_pledge_combined.csv`（`backfill_irb130_pledge.py`
回補的全市場sii+otc月頻董監質押彙總表）的股票子集），逐月計算兩個候選
訊號口徑（事前皆測，不用相關性結果挑）：
  1. `pledge_level`：`board_pledge_pct`（董監持股質押比例，%）原始水位。
  2. `pledge_mom`：同一檔股票相鄰月份`board_pledge_pct`的差分（百分點
     變化，MoM）。

**PIT時間差處理**：`#48`條目已查證揭露延遲約3週（例如113年06月資料於
113年07月22日發布），本腳本用保守的「該月月底再往後推一個月的月底」
當可得日（`_roc_to_asof`），確保早於實際發布日的緩衝，避免look-ahead。

**目標變數**：可得日之後（不含當日）N=20個交易日該股票自身forward報酬
（跟`factor_ic.py`預設`FORWARD_HORIZON`一致），用`adjusted_price_series`
（已holdout-safe capped在VAL_END）。

**事前綁定方向**：負（質押比例越高／近期上升，未來forward報酬越差）。

**判定標準（比照`#41`/`#42`/`#43`同一套train/val分期+時序洗牌null對照
框架）**：TRAIN=[universe起點, TRAIN_END]、VAL=(TRAIN_END, VAL_END]
（既有`validation/holdout.py`邊界），pooled panel Spearman相關係數，
N=200次洗牌null（整個panel打散訊號值、保留報酬配對，比照`#41`
`insider_holdings_pilot_ic.py`的做法，但這裡樣本量遠大於#41的15檔
pilot，屬正式第1關判準而非粗略pilot）。三項判準：(1)|corr|>0.02兩期皆
成立、(2)train/val皆符合事前綁定負相關方向、(3)VAL贏過洗牌null（單邊
percentile<=10.0）。

**主要指標的取捨**：事前用TRAIN期兩個訊號口徑各自的有效樣本數決定
（不看跟目標變數的相關性，避免事後選擇偏誤，比照
`institutional_concentration_gate.py::choose_primary_metric`同一原則）
——`pledge_level`每月皆有值、`pledge_mom`需要相鄰月份配對會損失每檔
股票的第一筆觀測，預期`pledge_level`樣本數較多。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from adjust import adjusted_price_series
from universe import universe as build_universe
from validation.holdout import TRAIN_END, VAL_END

DATA_PATH = Path(__file__).parent / "data" / "irb130_pledge_combined.csv"
SAMPLE_SIZE = 300
SAMPLE_SEED = 20260822  # 跟avg_pairwise_correlation_gate.py/institutional_concentration_gate.py同一批宇宙
FORWARD_HORIZON = 20
N_SHUFFLE = 200
SHUFFLE_SEED = 20260906
MIN_ABS_CORR = 0.02
EXPECTED_SIGN = -1  # 事前綁定：質押比例越高（或上升） -> 未來報酬應偏差（負相關）
START_DATE = "2010-01-01"


def _sample_universe_ids() -> list[str]:
    uni = build_universe()
    ids = sorted(uni["stock_id"].unique().tolist())
    rng = random.Random(SAMPLE_SEED)
    rng.shuffle(ids)
    return ids[:SAMPLE_SIZE]


def _roc_to_asof(roc_year, month) -> pd.Timestamp:
    """民國年月 -> 可得日（月底 + 1個月緩衝），避免look-ahead。"""
    west_year = int(roc_year) + 1911
    period = pd.Period(f"{west_year}-{int(month):02d}", freq="M")
    return (period + 1).end_time.normalize()


def load_pledge_panel(stock_ids: list[str]) -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, dtype={"co_id": str})
    df = df[df["co_id"].isin(stock_ids)].copy()
    if df.empty:
        return df
    df["as_of"] = df.apply(lambda r: _roc_to_asof(r["roc_year"], r["month"]), axis=1)
    df = df.sort_values(["co_id", "as_of"]).drop_duplicates(subset=["co_id", "as_of"], keep="last")
    return df.reset_index(drop=True)


def _forward_return(px: pd.DataFrame, as_of: pd.Timestamp, horizon: int) -> float | None:
    px = px.sort_values("date").reset_index(drop=True)
    dates = pd.to_datetime(px["date"]).to_numpy()
    idx = int(np.searchsorted(dates, np.datetime64(as_of), side="right"))
    if idx >= len(px):
        return None
    fwd_idx = idx + horizon
    if fwd_idx >= len(px):
        return None
    p0 = px["adj_close"].iloc[idx]
    p1 = px["adj_close"].iloc[fwd_idx]
    if p0 is None or p1 is None or pd.isna(p0) or pd.isna(p1) or p0 <= 0:
        return None
    return float(p1 / p0 - 1.0)


def build_signal_panel(pledge_raw: pd.DataFrame, stock_ids: list[str]) -> pd.DataFrame:
    rows = []
    price_cache: dict[str, pd.DataFrame] = {}
    for i, sid in enumerate(stock_ids):
        g = pledge_raw[pledge_raw["co_id"] == sid].sort_values("as_of").reset_index(drop=True)
        if len(g) < 2:
            continue
        g["pledge_mom"] = g["board_pledge_pct"].diff()
        try:
            if sid not in price_cache:
                price_cache[sid] = adjusted_price_series(sid, START_DATE)
        except Exception as e:  # noqa: BLE001 -- 單檔價格失敗不能讓整批中斷，跟其他gate同一套容錯
            print(f"  [{i + 1}/{len(stock_ids)}] {sid}: price ERROR ({e}), dropping")
            continue
        px = price_cache[sid]
        if px.empty:
            continue
        for _, r in g.iterrows():
            fwd = _forward_return(px, r["as_of"], FORWARD_HORIZON)
            if fwd is None:
                continue
            rows.append(
                {
                    "stock_id": sid,
                    "as_of": r["as_of"],
                    "pledge_level": float(r["board_pledge_pct"]),
                    "pledge_mom": float(r["pledge_mom"]) if pd.notna(r["pledge_mom"]) else np.nan,
                    "fwd_return": fwd,
                }
            )
        if (i + 1) % 50 == 0:
            print(f"  已處理 {i + 1}/{len(stock_ids)} 檔...")
    return pd.DataFrame(rows)


def _split(df: pd.DataFrame, col: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = df.dropna(subset=[col, "fwd_return"])
    train = d[d["as_of"] <= pd.Timestamp(TRAIN_END)]
    val = d[(d["as_of"] > pd.Timestamp(TRAIN_END)) & (d["as_of"] <= pd.Timestamp(VAL_END))]
    return train, val


def _shuffle_test(signal: np.ndarray, target: np.ndarray, n: int, seed: int) -> dict:
    """**2026-09-06本輪修正**：原本比照`day_trading_ratio_gate.py`/
    `institutional_concentration_gate.py`用單邊有號公式
    `pctl = 100*mean(shuffled >= real_corr)`，本輪用模擬資料實測驗證這個
    公式對「事前綁定負相關」的方向解讀是**反的**——真正很負的真實相關係數
    會讓幾乎全部洗牌null值都>=它，算出來percentile會接近100而非接近0，
    跟那兩支腳本註解宣稱的「percentile越低代表越顯著負相關」剛好相反
    （見`MARATHON_LOG.md`本輪心跳的完整模擬驗證記錄）。改用跟`factor_ic.py`
    （本佇列驗證最多次、最穩健的版本）同一套「取絕對值比較、方向另外用
    same_sign檢查」慣例，避免重蹈同一個方向性bug。"""
    real_corr, real_p = spearmanr(signal, target)
    rng = np.random.default_rng(seed)
    shuffled = np.empty(n)
    for i in range(n):
        perm = rng.permutation(signal)
        shuffled[i], _ = spearmanr(perm, target)
    # |real_corr|比多少比例的洗牌null更極端，方向另外用same_sign檢查（跟factor_ic.py一致）
    pctl = 100.0 * float(np.mean(np.abs(shuffled) < abs(real_corr)))
    return {
        "real_corr": float(real_corr),
        "real_p": float(real_p),
        "null_median": float(np.median(shuffled)),
        "percentile": pctl,
    }


def evaluate(df: pd.DataFrame, col: str, label: str) -> dict:
    signal = df[col].to_numpy()
    target = df["fwd_return"].to_numpy()
    shuf = _shuffle_test(signal, target, N_SHUFFLE, SHUFFLE_SEED)
    print(
        f"--- {label} (n={len(df)}) --- corr={shuf['real_corr']:+.4f} p={shuf['real_p']:.4f} "
        f"洗牌null(N={N_SHUFFLE})median={shuf['null_median']:+.4f} percentile={shuf['percentile']:.1f}"
    )
    return {"n": len(df), **shuf}


def run_metric(panel: pd.DataFrame, col: str, label: str) -> dict:
    train, val = _split(panel, col)
    print(f"\n### 訊號: {label} ({col}) ### TRAIN n={len(train)}  VAL n={len(val)}")
    if len(train) < 30 or len(val) < 30:
        print("樣本數過少（<30任一期），判定FAIL（結構性資料不足）")
        return {"verdict": "FAIL", "reason": "insufficient_sample", "train_n": len(train), "val_n": len(val)}
    train_r = evaluate(train, col, f"{label} TRAIN (<= {TRAIN_END})")
    val_r = evaluate(val, col, f"{label} VAL ({TRAIN_END} ~ {VAL_END})")

    train_sign_ok = (train_r["real_corr"] < 0) == (EXPECTED_SIGN < 0)
    val_sign_ok = (val_r["real_corr"] < 0) == (EXPECTED_SIGN < 0)
    same_sign = train_sign_ok and val_sign_ok
    nontrivial = abs(train_r["real_corr"]) > MIN_ABS_CORR and abs(val_r["real_corr"]) > MIN_ABS_CORR
    beats_null = val_r["percentile"] >= 90.0  # 取絕對值比較，方向已由same_sign獨立檢查（見_shuffle_test docstring修正說明）

    print(f"  === {label} 第1關cheap gate三項判準 ===")
    print(f"    1. 幅度非零 (|corr|>{MIN_ABS_CORR}兩期): {nontrivial}")
    print(f"    2. train/val皆符合事前綁定負相關方向: {same_sign} (TRAIN={train_r['real_corr']:+.4f}, VAL={val_r['real_corr']:+.4f})")
    print(f"    3. VAL |corr|贏過洗牌null(percentile>=90.0): {beats_null} (percentile={val_r['percentile']:.1f})")

    verdict = "CHEAP_PASS" if (nontrivial and same_sign and beats_null) else "FAIL"
    print(f"  [{label}] 判定: {verdict}")
    return {"train": train_r, "val": val_r, "verdict": verdict, "train_n": len(train), "val_n": len(val)}


def choose_primary_signal(panel: pd.DataFrame) -> tuple[str, dict]:
    """事前用TRAIN期原始訊號的有效樣本數決定主要指標，不看跟目標變數的相關性
    （避免事後挑選偏誤，比照institutional_concentration_gate.py同一原則）。"""
    train = panel[panel["as_of"] <= pd.Timestamp(TRAIN_END)]
    n_level = int(train["pledge_level"].notna().sum())
    n_mom = int(train["pledge_mom"].notna().sum())
    stats = {"pledge_level_n": n_level, "pledge_mom_n": n_mom}
    print("\n=== 事前指標樣本數比較（TRAIN期，未接觸目標變數） ===")
    print(f"  pledge_level: n={n_level}  pledge_mom: n={n_mom}")
    primary = "pledge_level" if n_level >= n_mom else "pledge_mom"
    print(f"  -> 選定主要指標: {primary}")
    return primary, stats


def main():
    print("=== #48 董監/大股東股權質押比例 regime/代理成本風險訊號 第1關cheap gate ===")
    stock_ids = _sample_universe_ids()
    print(f"抽樣{SAMPLE_SIZE}檔股票（seed={SAMPLE_SEED}，跟#42/#43同一批宇宙）...")

    pledge_raw = load_pledge_panel(stock_ids)
    matched_ids = sorted(pledge_raw["co_id"].unique().tolist()) if not pledge_raw.empty else []
    print(f"樣本{SAMPLE_SIZE}檔中{len(matched_ids)}檔在IRB130質押資料中有紀錄")
    if len(matched_ids) < 30:
        print("匹配樣本過少（<30檔），判定FAIL（結構性資料不足）")
        return {"verdict": "FAIL", "reason": "insufficient_matched_stocks", "n_matched": len(matched_ids)}

    print("載入價格序列並組裝訊號panel（可能需要數分鐘）...")
    panel = build_signal_panel(pledge_raw, matched_ids)
    print(f"對齊後panel: {len(panel)}筆觀測，涵蓋{panel['stock_id'].nunique() if not panel.empty else 0}檔股票")
    if len(panel) < 60:
        print("樣本過少（<60），判定FAIL（結構性資料不足）")
        return {"verdict": "FAIL", "reason": "insufficient_panel", "n": len(panel)}

    panel.to_csv(Path(__file__).parent / "data" / "irb130_pledge_signal_panel.csv", index=False)

    primary_signal, stability_stats = choose_primary_signal(panel)

    results = {
        "pledge_level": run_metric(panel, "pledge_level", "質押比例水位"),
        "pledge_mom": run_metric(panel, "pledge_mom", "質押比例MoM變化"),
    }

    final_verdict = results[primary_signal]["verdict"]
    print(f"\n=== 最終判定（依主要指標 {primary_signal}）: {final_verdict} ===")
    print("（另一指標僅供對照，不參與判定，避免事後挑選偏誤）")

    return {
        "primary_signal": primary_signal,
        "stability_stats": stability_stats,
        "n_matched_stocks": len(matched_ids),
        "n_panel": len(panel),
        "results": results,
        "verdict": final_verdict,
    }


if __name__ == "__main__":
    main()
