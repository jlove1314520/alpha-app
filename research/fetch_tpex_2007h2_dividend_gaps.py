"""補抓上櫃 2007H2 除權息對不到「無 FinMind 股利快取」的代號（每檔 1 次 FinMind 請求）。

代號清單讀 research/data/tpex_exright_2007h2_ref.json 的 unmatched（reason＝無 FinMind 股利快取），
快取寫成既有命名 research/data/raw/TaiwanStockDividend__{代號}__2006-01-01__2014-12-31.parquet，
已存在就不重抓。節流共用 data/rate_limit_state.json 的 finmind 來源（跨行程鎖、封鎖碼即停）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from backfill_price_history_gaps import (  # noqa: E402
    FINMIND_SOURCE_KEY, FINMIND_URL, _rate_limit_record_block, _rate_limit_wait_or_raise,
)

RAW = HERE / "data" / "raw"
REF = HERE / "data" / "tpex_exright_2007h2_ref.json"
S, E = "2006-01-01", "2014-12-31"


def main() -> int:
    ref = json.loads(REF.read_text(encoding="utf-8"))
    codes = sorted({u["code"] for u in ref["unmatched"] if u["reason"] == "無 FinMind 股利快取"})
    sent = 0
    for c in codes:
        out = RAW / f"TaiwanStockDividend__{c}__{S}__{E}.parquet"
        if out.exists():
            print(f"{c} 已有快取，略過", flush=True)
            continue
        try:
            _rate_limit_wait_or_raise()
        except RuntimeError as e:
            print(f"⚠️ 停止：{e}", flush=True)
            break
        r = requests.get(FINMIND_URL, params={"dataset": "TaiwanStockDividend", "data_id": c,
                                              "start_date": S, "end_date": E}, timeout=30)
        sent += 1
        if r.status_code in (402, 403, 428, 429):
            _rate_limit_record_block(FINMIND_SOURCE_KEY, r.status_code, r.text[:200])
            print(f"⚠️ FinMind HTTP {r.status_code}，已標記封鎖，停止", flush=True)
            break
        if r.status_code != 200:
            print(f"⚠️ {c} HTTP {r.status_code}，略過", flush=True)
            continue
        try:
            j = r.json()
        except ValueError:
            print(f"⚠️ {c} 回應不是 JSON，略過", flush=True)
            continue
        if j.get("msg") != "success":
            print(f"⚠️ {c} msg={j.get('msg')}，略過", flush=True)
            continue
        df = pd.DataFrame(j.get("data") or [])
        df.to_parquet(out, index=False)
        print(f"{c} {len(df)} 列", flush=True)
    print(f"共送出 {sent} 次請求", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
