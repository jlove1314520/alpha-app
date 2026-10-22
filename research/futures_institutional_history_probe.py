# -*- coding: utf-8 -*-
"""補.研究-期貨法人未平倉（2026-10-22）：第 10 關「資料源歷史起點探測」。

只做資料可得性探測，不算任何報酬、不碰 holdout。
端點：TAIFEX 官網「三大法人-區分各期貨契約」下載（www.taifex.com.tw/cht/3/futContractsDateDown，
POST queryStartDate／queryEndDate（YYYY/MM/DD）／commodityId=TXF，回 Big5 CSV）。
官方未公布次數上限；節流重用 research/paper_5_vrp_tracker.py 的 _get()（來源名 taifex_www，
同源 ≥3 秒、402/403/428/429 封鎖 2 小時不重試）。原始回應存 research/data/raw/taifex_fut_inst_probe/，
已抓過的不重抓（research/data/ 不進公開 repo）。
用法：python research/futures_institutional_history_probe.py 2001-01 2004-01 ...（每個月份 1 次請求，查該月 1～10 日）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw" / "taifex_fut_inst_probe"
URL = "https://www.taifex.com.tw/cht/3/futContractsDateDown"


def fetch(ym: str) -> bytes:
    f = RAW / f"TXF_{ym}.csv"
    if f.exists():
        return f.read_bytes()
    sys.path.insert(0, str(HERE))
    from paper_5_vrp_tracker import _get  # 共用節流
    y, m = ym.split("-")
    r = _get("taifex_www", "POST", URL, data={
        "queryStartDate": f"{y}/{m}/01", "queryEndDate": f"{y}/{m}/10", "commodityId": "TXF"})
    RAW.mkdir(parents=True, exist_ok=True)
    f.write_bytes(r.content)
    return r.content


def summarize(raw: bytes) -> dict:
    text = raw.decode("big5", errors="replace") if not raw.startswith(b"\xef\xbb\xbf") else raw.decode("utf-8-sig")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    is_csv = bool(lines) and "," in lines[0] and "<html" not in text[:500].lower()
    dates = sorted({ln.split(",")[0] for ln in lines[1:]}) if is_csv else []
    return {"bytes": len(raw), "is_csv": is_csv, "header": lines[0][:200] if lines else "",
            "rows": max(len(lines) - 1, 0) if is_csv else 0, "dates": dates[:3] + (["…"] if len(dates) > 3 else []),
            "head_text": "" if is_csv else text[:200]}


def main() -> int:
    out = {}
    for ym in sys.argv[1:]:
        try:
            out[ym] = summarize(fetch(ym))
        except Exception as e:  # noqa: BLE001 探測腳本：單月失敗只記錄
            out[ym] = {"error": repr(e)[:200]}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
