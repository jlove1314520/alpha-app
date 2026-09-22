# -*- coding: utf-8 -*-
"""#77 美國高收益債利差（High-Yield Credit Spread）regime訊號——資料源
歷史起點探測（七之三第10關）。

零判定、零相關性計算，只確認FRED `BAMLH0A0HYM2`（ICE BofA US High Yield
Index Option-Adjusted Spread）序列的實際歷史起點與涵蓋範圍是否早於
train/val邊界（TRAIN_END=2020-12-31），若起點晚於邊界則直接判「只能前向
觀察」，不得跳過此步驟直接假設可行（`HYPOTHESIS_QUEUE.md` #77條目事前
明訂）。

只讀FRED公開端點（金鑰讀自凍結區`C:\\alpha\\alpha-data\\fred_key.txt.txt`，
只讀不動、不複製進輸出檔），不觸碰holdout（不主動下載VAL_END之後的資料，
但FRED端點本身不支援observation_end參數用於本探測——實際判定沿用既有
`fred_yield_curve_gate.py` house style：raw fetch可能含近期資料，但
本探測只印統計摘要，不做任何拿holdout資料的判定運算）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

FRED_KEY_PATH = Path(r"C:\alpha\alpha-data\fred_key.txt.txt")
FRED_SERIES = "BAMLH0A0HYM2"
FRED_START = "1996-01-01"  # 文獻記載該序列起點約1996-12-31，故意提早一點探測
TRAIN_END = "2020-12-31"
VAL_END = "2024-12-31"


def _read_fred_key() -> str:
    if not FRED_KEY_PATH.exists():
        raise RuntimeError(f"找不到FRED金鑰檔案: {FRED_KEY_PATH}（凍結區檔案，探測無法起跑）")
    key = FRED_KEY_PATH.read_text(encoding="utf-8").strip()
    if not key:
        raise RuntimeError(f"FRED金鑰檔案為空: {FRED_KEY_PATH}")
    return key


def probe(series_id: str, start_date: str) -> dict:
    try:
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
        obs = payload.get("observations", [])
        if not obs:
            return {"series_id": series_id, "ok": False, "reason": "empty_observations"}
        df = pd.DataFrame(obs)[["date", "value"]]
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["value"]).sort_values("date").reset_index(drop=True)
        if df.empty:
            return {"series_id": series_id, "ok": False, "reason": "all_values_missing_after_dropna"}

        first_date = str(df["date"].min().date())
        last_date = str(df["date"].max().date())
        n_before_train_end = int((df["date"] <= pd.Timestamp(TRAIN_END)).sum())
        n_train_to_val = int(
            ((df["date"] > pd.Timestamp(TRAIN_END)) & (df["date"] <= pd.Timestamp(VAL_END))).sum()
        )
        starts_before_train_end = df["date"].min() <= pd.Timestamp(TRAIN_END)

        return {
            "series_id": series_id,
            "ok": True,
            "first_date": first_date,
            "last_date": last_date,
            "n_rows_total": int(len(df)),
            "n_rows_train_period": n_before_train_end,
            "n_rows_val_period": n_train_to_val,
            "starts_before_train_end": bool(starts_before_train_end),
            "gate7of10_verdict": "PASS_起點早於TRAIN_END可開發完整SPEC"
            if starts_before_train_end
            else "FAIL_只能前向觀察",
        }
    except Exception as e:
        return {"series_id": series_id, "ok": False, "reason": f"exception:{type(e).__name__}:{e}"}


def main():
    result = {
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "train_end_boundary": TRAIN_END,
        "val_end_boundary": VAL_END,
        "series": probe(FRED_SERIES, FRED_START),
    }

    out_path = Path(__file__).parent / "hy_credit_spread_probe_result.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
