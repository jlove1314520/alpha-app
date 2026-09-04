"""`HYPOTHESIS_QUEUE.md` #33 美國公債殖利率曲線（10Y-2Y利差）當全球風險
regime訊號 第1關cheap gate。

經濟理由：美國公債殖利率曲線倒掛（10年期減2年期利差轉負）是總經文獻裡最
穩健的衰退領先指標之一（Estrella & Mishkin 1996，NY Fed衰退機率模型的
核心輸入），機制是市場對未來短期利率路徑的集體預期。跟本佇列已測過的32條
假設不同——這是第一次引入公債市場的資訊（前面用過股票市場本身、選擇權
部位#31、外匯#32，但都不是公債殖利率）。台灣是高度依賴出口、外資持股占比
高的小型開放經濟體，美國衰退風險升高時全球risk-off情緒同步壓抑台股本益比
與資金流入。完整經濟理由見`HYPOTHESIS_QUEUE.md` #33條目。

跟`fx_twd_gate.py`（#32）/`option_pcr_gate.py`（#31）同一種指數層級
（index-level）時序相關性測試精神，不是`factor_ic.py`的cross-sectional
選股IC——測的是「T10Y2Y利差水位本身」這一條時間序列跟「TAIEX後續M個交易日
報酬」這一條時間序列之間的相關性。

**訊號口徑決定（本輪方法論選擇，事前綁定，第1關前決定）**：訊號用**利差
水位本身**（level），不是N日變動率——跟`fx_twd_gate.py`（用N日變動率）
刻意不同，理由是這條假設在`HYPOTHESIS_QUEUE.md`裡明確定義的機制是「曲線
形狀本身代表的市場預期」（倒掛與否是一個狀態，不是變動速度），跟外匯資金
外流（一個流量/速度機制）經濟意義不同，訊號口徑要對應各自的機制定義，不能
機械套用同一種變動率公式。

**訊號/目標窗口（事前綁定，第1關前決定，非跑完看結果才選）**：M=20交易日
（預測視窗）——與本專案既有regime類窗口（`regime_overlay.py`20日波動度窗、
`fx_twd_gate.py`/`option_pcr_gate.py`同量級）同一個量級，經濟理由是殖利率
曲線是慢變數（利率預期不會逐日劇烈翻轉），用月頻量級窗口比單日更貼近這個
機制的時間尺度，不用#31（選擇權部位，次日窗口）那種高頻窗口——那條的部位
資訊是每日更新的市場情緒，這條是利率路徑預期，時間尺度不同。訊號 = T10Y2Y
[t]（FRED原始序列已直接是利差，不需自行相減）；目標 = TAIEX[t+M]/TAIEX[t]
- 1（訊號日t之後M個交易日的台股報酬，訊號在t日已完全確定，預測未來，無
未來函數）。

**事前綁定方向**：利差水位本身應與未來報酬**正相關**（利差走低/轉負=市場
預期衰退風險上升=未來報酬應該轉弱；利差高/曲線正常=風險預期低=未來報酬
應該較佳）——這個方向要在第1關前寫進本docstring事前綁定，不能事後配合
結果調整。

**判定標準（比照本佇列既有cheap gate三項判準：幅度非零/train-val同號/
贏過洗牌null，跟#19/#31/#32完全同一套框架）**：TRAIN=[universe起點,
TRAIN_END]、VAL=(TRAIN_END, VAL_END]（既有`validation/holdout.py`邊界），
皆用Pearson相關係數（主要）+ Spearman（穩健性檢查），N_SHUFFLE=500次洗牌
null（打散訊號時序、保留TAIEX報酬時序）。

**金鑰處理**：讀取`C:\\alpha\\alpha-data\\fred_key.txt.txt`（凍結區檔案，
只讀不動，不複製內容進任何會被commit的檔案或log，只在記憶體內使用）。

**已知相關背景（誠實揭露，避免跟已FAIL的timing類別誤判為同一套）**：
跟已FAIL的#10（大盤200日均線/波動度）、#15（波動度目標化）、#19（美股
隔夜報酬）、#26（融資餘額）、#28（市場廣度）、#31（選擇權PCR）、#32
（台幣匯率）皆不同資訊來源；本佇列regime/timing類假設至今全數FAIL，這條
同樣可能複製同一種死法（第1關cheap gate過但轉具體overlay後在成本/參數
高原/逐年一致性關卡死亡），需要誠實面對這個可能性。

2026-09-05 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#33第1關
起跑。
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from scipy import stats

from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END

N_SHUFFLE = 500
SHUFFLE_SEED = 20260905
FRED_SERIES = "T10Y2Y"
FRED_START = "2015-01-01"
M_TARGET_DAYS = 20   # TAIEX後續M日報酬預測視窗

FRED_KEY_PATH = Path(r"C:\alpha\alpha-data\fred_key.txt.txt")
DATA_DIR = Path(__file__).parent / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)
_CACHE_MAX_AGE_SECONDS = 24 * 3600  # 日頻總經序列，24小時快取足夠新鮮


def _read_fred_key() -> str:
    if not FRED_KEY_PATH.exists():
        raise RuntimeError(f"找不到FRED金鑰檔案: {FRED_KEY_PATH}（凍結區檔案，第1關無法起跑）")
    key = FRED_KEY_PATH.read_text(encoding="utf-8").strip()
    if not key:
        raise RuntimeError(f"FRED金鑰檔案為空: {FRED_KEY_PATH}")
    return key


def _cache_path(series_id: str, start_date: str) -> Path:
    raw = f"{series_id}_{start_date}"
    h = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return DATA_DIR / f"FRED_{series_id}_{h}.json"


def fetch_fred_series(series_id: str, start_date: str) -> pd.DataFrame:
    """回傳 columns: date(Timestamp,已排序), value(float)。

    FRED `fred/series/observations` 端點，日頻。「.」代表當天無觀測值
    （例如假日），丟棄。快取存raw JSON，key不落地到快取檔案本身（快取
    檔名只含series_id/start_date的hash，不含金鑰）。
    """
    cache_path = _cache_path(series_id, start_date)
    if cache_path.exists() and (time.time() - cache_path.stat().st_mtime) < _CACHE_MAX_AGE_SECONDS:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        key = _read_fred_key()
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "api_key": key,
            "file_type": "json",
            "observation_start": start_date,
        }
        r = requests.get(url, params=params, timeout=20.0)
        r.raise_for_status()
        payload = r.json()
        cache_path.write_text(json.dumps(payload), encoding="utf-8")

    obs = payload.get("observations", [])
    if not obs:
        raise RuntimeError(f"FRED {series_id} 回傳無observations，第1關無法起跑")
    df = pd.DataFrame(obs)[["date", "value"]]
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")  # "." -> NaN
    df = df.dropna(subset=["value"]).sort_values("date").reset_index(drop=True)
    return df


def build_aligned_series() -> pd.DataFrame:
    """對每個有效訊號日t（需要t有T10Y2Y值且t+M存在），配對利差水位(訊號)
    跟TAIEX M日後報酬(目標)。回傳 columns: date, spread_level, tw_fwd_ret_m。
    """
    fred = fetch_fred_series(FRED_SERIES, FRED_START)
    fred = fred.rename(columns={"value": "spread_level"})

    tw = fetch_yf_index(ticker="^TWII", start_date="2010-01-01")
    tw = tw.dropna(subset=["close"]).copy()
    tw["date"] = pd.to_datetime(tw["date"])
    tw = tw.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)
    tw["tw_fwd_ret_m"] = tw["close"].shift(-M_TARGET_DAYS) / tw["close"] - 1.0

    merged = pd.merge(
        fred[["date", "spread_level"]],
        tw[["date", "tw_fwd_ret_m"]],
        on="date",
        how="inner",
    )
    merged = merged.dropna(subset=["spread_level", "tw_fwd_ret_m"]).reset_index(drop=True)
    return merged


def _split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[df["date"] <= pd.Timestamp(TRAIN_END)].copy()
    val = df[(df["date"] > pd.Timestamp(TRAIN_END)) & (df["date"] <= pd.Timestamp(VAL_END))].copy()
    return train, val


def _shuffle_percentile(signal: np.ndarray, target: np.ndarray, n: int, seed: int) -> dict:
    real_pearson, real_p = stats.pearsonr(signal, target)
    rng = np.random.default_rng(seed)
    shuffled = np.empty(n)
    for i in range(n):
        perm = rng.permutation(signal)
        shuffled[i] = stats.pearsonr(perm, target)[0]
    pctl = 100.0 * float(np.mean(np.abs(shuffled) <= abs(real_pearson)))
    return {
        "pearson": float(real_pearson),
        "pearson_p": float(real_p),
        "null_median_abs": float(np.median(np.abs(shuffled))),
        "percentile": pctl,
    }


def evaluate(df: pd.DataFrame, label: str) -> dict:
    signal = df["spread_level"].to_numpy()
    target = df["tw_fwd_ret_m"].to_numpy()
    n = len(df)
    pearson, pearson_p = stats.pearsonr(signal, target)
    spearman, spearman_p = stats.spearmanr(signal, target)
    shuf = _shuffle_percentile(signal, target, N_SHUFFLE, SHUFFLE_SEED)
    print(f"\n--- {label} (n={n}) ---")
    print(f"  Pearson r={pearson:+.4f} (p={pearson_p:.4f})")
    print(f"  Spearman rho={spearman:+.4f} (p={spearman_p:.4f})")
    print(f"  洗牌null(N={N_SHUFFLE}): median|r|={shuf['null_median_abs']:.4f}  "
          f"真實|r|percentile={shuf['percentile']:.1f}")
    return {
        "label": label, "n": n, "pearson": pearson, "pearson_p": pearson_p,
        "spearman": spearman, "spearman_p": spearman_p,
        "null_percentile": shuf["percentile"], "null_median_abs": shuf["null_median_abs"],
    }


def main():
    aligned = build_aligned_series()
    print(f"對齊後總配對數: {len(aligned)}")
    print(f"日期範圍: {aligned['date'].min()} ~ {aligned['date'].max()}")
    print(f"T10Y2Y利差水位描述統計: mean={aligned['spread_level'].mean():.4f} "
          f"median={aligned['spread_level'].median():.4f} std={aligned['spread_level'].std():.4f} "
          f"min={aligned['spread_level'].min():.4f} max={aligned['spread_level'].max():.4f}")
    print(f"TAIEX後M({M_TARGET_DAYS})日報酬描述統計: mean={aligned['tw_fwd_ret_m'].mean():.4f} "
          f"median={aligned['tw_fwd_ret_m'].median():.4f} std={aligned['tw_fwd_ret_m'].std():.4f}")

    train, val = _split(aligned)
    print(f"\nTRAIN(<= {TRAIN_END}): n={len(train)}  VAL({TRAIN_END}~{VAL_END}): n={len(val)}")

    if len(train) < 30 or len(val) < 30:
        print("\n樣本數過少（<30），資料可能不完整，判定FAIL（結構性資料不足）")
        return {"verdict": "FAIL", "reason": "insufficient_sample", "train_n": len(train), "val_n": len(val)}

    train_result = evaluate(train, f"TRAIN (<= {TRAIN_END})")
    val_result = evaluate(val, f"VAL ({TRAIN_END} ~ {VAL_END})")

    same_sign = (train_result["pearson"] > 0) == (val_result["pearson"] > 0)
    nontrivial = abs(train_result["pearson"]) > 0.01 and abs(val_result["pearson"]) > 0.01
    beats_null = val_result["null_percentile"] >= 90.0
    matches_expected_direction = val_result["pearson"] > 0  # 事前綁定：利差水位高本身應與未來報酬正相關

    print("\n=== 第1關cheap gate三項判準 ===")
    print(f"  1. 幅度非零 (|r|>0.01兩期): {nontrivial}")
    print(f"  2. train/val同號: {same_sign} (TRAIN r={train_result['pearson']:+.4f}, "
          f"VAL r={val_result['pearson']:+.4f})")
    print(f"  3. VAL贏過洗牌null(percentile>=90.0): {beats_null} "
          f"(percentile={val_result['null_percentile']:.1f})")
    print(f"  （附註，非判準本身）VAL方向是否符合事前預期(正相關): {matches_expected_direction}")

    verdict = "CHEAP_PASS" if (same_sign and nontrivial and beats_null) else "FAIL"
    print(f"\n判定: {verdict}")

    aligned.to_csv("data/fred_yield_curve_aligned.csv", index=False)
    return {"train": train_result, "val": val_result, "verdict": verdict,
            "matches_expected_direction": matches_expected_direction}


if __name__ == "__main__":
    main()
