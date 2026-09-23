# -*- coding: utf-8 -*-
"""#81 國發會景氣對策信號——資料源歷史起點探測（七之三第10關）。

零判定、零相關性計算，只確認官方開放資料端點是否可程式化存取、資料涵蓋
範圍是否早於train/val邊界（TRAIN_END=2020-12-31），若晚於邊界則直接判
「只能前向觀察」，不得跳過此步驟直接假設可行（`HYPOTHESIS_QUEUE.md`
#81條目事前明訂）。

資料源：data.gov.tw dataset 6099（景氣指標及燈號，國發會發布），透過
v2 REST API取得實際下載URL（`ws.ndc.gov.tw/Download.ashx?...`，官方本身
托管，非第三方鏡像），下載ZIP解壓後讀取「景氣指標與燈號.csv」的
「景氣對策信號綜合分數」欄位。

只讀官方公開端點，免驗證、免CAPTCHA，不觸碰holdout（不做任何判定運算，
只印統計摘要）。
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DATASET_API = "https://data.gov.tw/api/v2/rest/dataset/6099"
TRAIN_END = "2020-12-31"
VAL_END = "2024-12-31"
CACHE_CSV = Path(__file__).parent.parent / "data" / "ndc_business_signal_raw.csv"


def resolve_download_url() -> str:
    resp = requests.get(DATASET_API, timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    dist = payload["result"]["distribution"][0]
    return dist["resourceDownloadUrl"]


def fetch_light_signal_csv() -> bytes:
    url = resolve_download_url()
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    return zf.read("景氣指標與燈號.csv")


def parse_rows(raw_csv: bytes) -> list[dict]:
    text = raw_csv.decode("utf-8-sig")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    header = [h.strip('"') for h in lines[0].split(",")]
    idx_date = header.index("Date")
    idx_score = header.index("景氣對策信號綜合分數")
    idx_light = header.index("景氣對策信號")
    rows = []
    for ln in lines[1:]:
        parts = ln.split(",")
        if len(parts) <= max(idx_date, idx_score, idx_light):
            continue
        yyyymm = parts[idx_date].strip('"')
        score_raw = parts[idx_score].strip('"')
        light_raw = parts[idx_light].strip('"')
        if score_raw == "-" or light_raw == "-":
            continue
        try:
            score = float(score_raw)
        except ValueError:
            continue
        rows.append({"yyyymm": yyyymm, "score": score, "light": light_raw})
    return rows


def main():
    result = {
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "train_end_boundary": TRAIN_END,
        "val_end_boundary": VAL_END,
        "dataset_api": DATASET_API,
    }
    try:
        raw = fetch_light_signal_csv()
        CACHE_CSV.write_bytes(raw)
        rows = parse_rows(raw)
        if not rows:
            result["ok"] = False
            result["reason"] = "no_valid_rows_after_filtering_dash_placeholders"
        else:
            first = rows[0]["yyyymm"]
            last = rows[-1]["yyyymm"]
            first_date = f"{first[:4]}-{first[4:]}-01"
            n_train = sum(1 for r in rows if r["yyyymm"] <= "202012")
            n_val = sum(1 for r in rows if "202101" <= r["yyyymm"] <= "202412")
            result.update(
                {
                    "ok": True,
                    "n_rows_total_with_real_score": len(rows),
                    "first_yyyymm_with_real_score": first,
                    "last_yyyymm_with_real_score": last,
                    "n_rows_train_period": n_train,
                    "n_rows_val_period": n_val,
                    "starts_before_train_end": first_date <= TRAIN_END,
                    "gate7of10_verdict": (
                        "PASS_月頻歷史起點遠早於TRAIN_END可開發完整SPEC"
                        if first_date <= TRAIN_END
                        else "FAIL_只能前向觀察"
                    ),
                    "cache_file": str(CACHE_CSV),
                    "pit_note": (
                        "資料為月頻，本檔尚未含公布延遲欄位（國發會官方於"
                        "每月27日左右公布上上個月分數，下一輪cheap gate須"
                        "自行加上公布延遲位移，不得用統計期間末日直接對齊）"
                    ),
                }
            )
    except Exception as e:  # noqa: BLE001 —— 探測腳本本身失敗只降級回報，不中斷排程
        result["ok"] = False
        result["reason"] = f"exception:{type(e).__name__}:{e}"

    out_path = Path(__file__).parent / "ndc_business_signal_probe_result.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
