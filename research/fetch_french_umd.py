# -*- coding: utf-8 -*-
"""Kenneth French Data Library 動能因子（UMD／Mom）月報酬 → 本機參考序列（先.八十六-2b，2026-10-14）。

用途：B1（f_us_momentum_12m）的「現象是否存在」對照。**不是新試驗、不計 N**，不登記 TRIALS_LEDGER。

來源：Dartmouth Tuck 官方 Data Library
  https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
  檔案 ftp/F-F_Momentum_Factor_CSV.zip（約 5.6KB），一次 1 個請求；robots.txt 未禁止該路徑；
  官方未公布次數上限。資料公開免費，引用時註明 Kenneth R. French Data Library。

輸出（research/data 已 gitignore，只存本機）：
  research/data/raw/french/F-F_Momentum_Factor_CSV.zip（原檔）
  research/data/french_umd_monthly.json（月報酬 %，含原檔標頭說明與下載時間）
CSV 結構：說明文字 → 「,Mom」表頭 → YYYYMM,值（月）→ 空行 → Annual Factors 段（年）。只取月資料段。
"""
from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw" / "french"
OUT = HERE / "data" / "french_umd_monthly.json"
URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_CSV.zip"
TZ = timezone(timedelta(hours=8))


def parse(text: str) -> tuple[list[str], dict[str, float]]:
    lines = text.splitlines()
    header_idx = next(i for i, l in enumerate(lines) if re.match(r"^\s*,\s*Mom\s*$", l))
    notes = [l.strip() for l in lines[:header_idx] if l.strip()]
    monthly: dict[str, float] = {}
    for l in lines[header_idx + 1:]:
        m = re.match(r"^\s*(\d{6})\s*,\s*(-?\d+(?:\.\d+)?)\s*$", l)
        if not m:
            break  # 月資料段結束（空行或 Annual Factors 段）
        ym = m.group(1)
        monthly[f"{ym[:4]}-{ym[4:]}"] = float(m.group(2))
    return notes, monthly


def main() -> int:
    r = requests.get(URL, timeout=60)
    r.raise_for_status()
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "F-F_Momentum_Factor_CSV.zip").write_bytes(r.content)
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    name = zf.namelist()[0]
    notes, monthly = parse(zf.read(name).decode("latin-1"))
    if len(monthly) < 1000:
        print(f"[error] 月資料只有 {len(monthly)} 筆，格式可能變了；不寫輸出")
        return 1
    keys = sorted(monthly)
    doc = {"generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
           "source": URL, "file": name, "last_modified": r.headers.get("last-modified"),
           "unit": "月報酬（%）", "factor": "Mom（UMD）", "notes": notes,
           "first_month": keys[0], "last_month": keys[-1], "n_months": len(keys),
           "purpose": "B1 現象對照的參考序列；不是新試驗、不計 N",
           "monthly": {k: monthly[k] for k in keys}}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"UMD 月報酬 {keys[0]}～{keys[-1]} 共 {len(keys)} 個月 → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
