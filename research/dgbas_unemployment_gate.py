"""`HYPOTHESIS_QUEUE.md` #80 台灣失業率YoY當TAIEX regime降曝險訊號
第1關cheap gate。

經濟理由：勞動市場走弱（失業率年增惡化）→ 內需轉弱→股市承壓，跟本佇列
已測過的#31~#34/#76~#78同一種「index-level時序相關性」測試精神，非
cross-sectional選股IC。

**操作性定義（依#80續1事前綁定，尚未看任何報酬前修正）**：因原定義「就業
人數年增率」查無可程式化來源，改用已確認可行的DGBAS「失業率」水準之
YoY差值（百分點差，非成長率）。事前綁定方向反轉：失業率YoY上升（惡化）
→ TAIEX後續報酬應**負相關**。

**訊號口徑**：月頻失業率總計欄位（`總計_Total_百分比`），YoY = rate[t] -
rate[t-12個月]（百分點差）。

**發布延遲（事前綁定，避免未來函數）**：DGBAS人力資源調查確切公布日規則
未查證，依#80續1裁示採保守估計：訊號在該月最後一天之後T+30天才視為
市場已知（`PUBLISH_LAG_DAYS=30`）。

**目標窗口**：M=20交易日，TAIEX[t+M]/TAIEX[t]-1，跟#76/#77/#78同量級。

**判定標準**：TRAIN/VAL依`validation/holdout.py`既有邊界，Pearson為主+
Spearman穩健性檢查，N_SHUFFLE=500（月頻訊號但merge到日頻TAIEX後，同一
signal值連續重複多個交易日，這件事本身不改變洗牌檢定的有效性——洗牌是
打散signal時序後重新配對，重複值只影響sample n不影響檢定邏輯本身；
有效自由度議題留待CHEAP_PASS後續關卡再處理，第1關沿用既有N_SHUFFLE=500
慣例不特別調整，跟#77/#79前置未備前的既有慣例一致）。

**資料源**：DGBAS人力資源調查失業率官方XML
`https://ws.dgbas.gov.tw/001/Upload/461/relfile/11525/230038/mp0101a07.xml`
（#80續1已查證免認證/免CAPTCHA/1978年起連續至2026M08）；TAIEX用
`yf_price_client.py::fetch_yf_index()`既有基礎設施（ticker=`^TWII`）。

2026-09-23 由`HYPOTHESIS_QUEUE_PROTOCOL.md`第1節自動排程接續，佇列#80
「下一輪待辦(a)(b)」執行。
"""
from __future__ import annotations

import re
import ssl
import xml.etree.ElementTree as ET
from datetime import timedelta

import numpy as np
import pandas as pd
import requests
from scipy import stats

# 已知SSL陷阱（CLAUDE.md「央行外匯局」節同一模式）：部分gov.tw中繼CA缺
# Subject Key Identifier擴充欄位，requests預設驗證會拋
# CERTIFICATE_VERIFY_FAILED；修法為只關閉VERIFY_X509_STRICT旗標，
# 不整個關閉憑證驗證（非verify=False）。
_ctx = ssl.create_default_context()
_ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT


class _GovTwAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = _ctx
        return super().init_poolmanager(*args, **kwargs)


_session = requests.Session()
_session.mount("https://", _GovTwAdapter())

from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END

N_SHUFFLE = 500
SHUFFLE_SEED = 20260923
TAIEX_TICKER = "^TWII"
DATA_START = "1978-01-01"
M_TARGET_DAYS = 20
PUBLISH_LAG_DAYS = 30
XML_URL = "https://ws.dgbas.gov.tw/001/Upload/461/relfile/11525/230038/mp0101a07.xml"
MONTH_RE = re.compile(r"^(\d{4})M(\d{2})$")


def fetch_unemployment_rate() -> pd.DataFrame:
    """下載DGBAS失業率XML，篩選月度列（排除年度彙總列），回傳
    columns: month_end(該月最後一天), rate(失業率總計百分比,浮點數)。
    """
    resp = _session.get(XML_URL, timeout=30)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    rows = []
    for row in root:
        period_val = None
        rate_val = None
        for child in row:
            if child.tag.endswith("_Year_and_month"):
                period_val = (child.text or "").strip()
            elif child.tag.endswith("_Total_") or "Total_" in child.tag:
                if rate_val is None:
                    rate_val = (child.text or "").strip()
        if period_val is None or rate_val is None:
            continue
        m = MONTH_RE.match(period_val)
        if not m:
            continue
        year, month = int(m.group(1)), int(m.group(2))
        try:
            rate = float(rate_val)
        except ValueError:
            continue
        rows.append({"year": year, "month": month, "rate": rate})

    if not rows:
        raise RuntimeError("DGBAS XML未解析出任何月度列，第1關無法起跑")

    df = pd.DataFrame(rows).drop_duplicates(subset=["year", "month"]).sort_values(["year", "month"])
    df["month_end"] = pd.to_datetime(df["year"].astype(str) + "-" + df["month"].astype(str) + "-01") \
        + pd.offsets.MonthEnd(0)
    return df[["month_end", "rate"]].reset_index(drop=True)


def build_aligned_series() -> pd.DataFrame:
    unemp = fetch_unemployment_rate()
    unemp = unemp.sort_values("month_end").reset_index(drop=True)
    unemp["rate_yoy"] = unemp["rate"] - unemp["rate"].shift(12)
    unemp = unemp.dropna(subset=["rate_yoy"]).copy()
    unemp["available_date"] = unemp["month_end"] + timedelta(days=PUBLISH_LAG_DAYS)
    unemp = unemp[["available_date", "rate_yoy"]].sort_values("available_date").reset_index(drop=True)

    tw = fetch_yf_index(ticker=TAIEX_TICKER, start_date=DATA_START)
    if tw.empty:
        raise RuntimeError("TAIEX(^TWII)抓取後為空資料，第1關無法起跑")
    tw = tw.dropna(subset=["close"]).copy()
    tw["date"] = pd.to_datetime(tw["date"])
    tw = tw.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)
    tw["tw_fwd_ret_m"] = tw["close"].shift(-M_TARGET_DAYS) / tw["close"] - 1.0

    merged = pd.merge_asof(
        tw[["date", "tw_fwd_ret_m"]],
        unemp.rename(columns={"available_date": "date", "rate_yoy": "unemp_yoy"}),
        on="date", direction="backward",
    )
    merged = merged.dropna(subset=["unemp_yoy", "tw_fwd_ret_m"]).reset_index(drop=True)
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
    return {"pearson": float(real_pearson), "pearson_p": float(real_p),
            "null_median_abs": float(np.median(np.abs(shuffled))), "percentile": pctl}


def evaluate(df: pd.DataFrame, label: str) -> dict:
    signal = df["unemp_yoy"].to_numpy()
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
    return {"label": label, "n": n, "pearson": pearson, "pearson_p": pearson_p,
            "spearman": spearman, "spearman_p": spearman_p,
            "null_percentile": shuf["percentile"], "null_median_abs": shuf["null_median_abs"]}


def main():
    aligned = build_aligned_series()
    print(f"對齊後總配對數: {len(aligned)}")
    print(f"日期範圍: {aligned['date'].min()} ~ {aligned['date'].max()}")
    print(f"失業率YoY(百分點差)描述統計: mean={aligned['unemp_yoy'].mean():.4f} "
          f"median={aligned['unemp_yoy'].median():.4f} std={aligned['unemp_yoy'].std():.4f} "
          f"min={aligned['unemp_yoy'].min():.4f} max={aligned['unemp_yoy'].max():.4f}")

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
    matches_expected_direction = val_result["pearson"] < 0  # 事前綁定：失業率YoY上升→TAIEX後續報酬負相關

    print("\n=== 第1關cheap gate三項判準 ===")
    print(f"  1. 幅度非零 (|r|>0.01兩期): {nontrivial}")
    print(f"  2. train/val同號: {same_sign} (TRAIN r={train_result['pearson']:+.4f}, "
          f"VAL r={val_result['pearson']:+.4f})")
    print(f"  3. VAL贏過洗牌null(percentile>=90.0): {beats_null} "
          f"(percentile={val_result['null_percentile']:.1f})")
    print(f"  （附註，非判準本身）VAL方向是否符合事前預期(負相關): {matches_expected_direction}")

    verdict = "CHEAP_PASS" if (same_sign and nontrivial and beats_null) else "FAIL"
    print(f"\n判定: {verdict}")

    aligned.to_csv("data/dgbas_unemployment_aligned.csv", index=False)
    return {"train": train_result, "val": val_result, "verdict": verdict,
            "matches_expected_direction": matches_expected_direction}


if __name__ == "__main__":
    main()
