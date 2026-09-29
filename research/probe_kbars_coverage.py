"""分K.零 探針：呼叫本機 /live/kbars（既有機制，不開第二條連線）測試涵蓋範圍。

**範疇（本次只測這個子問題）**：涵蓋哪些標的（上市/上櫃/ETF/已下市各3檔）。
不測「最多回溯多久」——現有 shioaji_quotes.py 的 op="kbars" 協定寫死
`api.kbars(contract, start=day, end=day)`（day=今天），沒有 start/end 參數可傳，
要測回溯需要先改常駐行程協定並重啟，是下一個工作單位，見 PENDING_QUEUE.md
「分K.零」條目的下一步。

用法：python research/probe_kbars_coverage.py
"""
import json
import time
from pathlib import Path

import requests

TOKEN = Path(__file__).with_name(".alpha_live_token").read_text(encoding="utf-8").strip()
BASE = "http://127.0.0.1:8001"
HEADERS = {"X-Alpha-Local-Token": TOKEN}

CASES = [
    ("上市", "2412", "中華電"),
    ("上市", "1101", "台泥"),
    ("上市", "2882", "國泰金"),
    ("上櫃", "6547", "高端疫苗"),
    ("上櫃", "4966", "譜瑞-KY"),
    ("上櫃", "8299", "群聯"),
    ("ETF", "0050", "元大台灣50"),
    ("ETF", "0056", "元大高股息"),
    ("ETF", "00878", "國泰永續高股息"),
    ("已下市", "6452", "康友-KY"),
    ("已下市", "3662", "樂陞"),
    ("已下市", "4803", "VHQ-KY"),
]


def health():
    r = requests.get(f"{BASE}/health", headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()


def kbars(code: str):
    r = requests.get(f"{BASE}/live/kbars", params={"code": code}, headers=HEADERS, timeout=15)
    return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text)


def main():
    h0 = health()
    print(f"[開始前] kbars_usage={h0.get('kbars_usage')}, shioaji_connected={h0.get('shioaji_connected')}")
    results = []
    for market, code, name in CASES:
        t0 = time.time()
        try:
            status, body = kbars(code)
        except Exception as e:  # noqa: BLE001 — 探針腳本，任何一檔失敗都不能拖垮其他檔
            status, body = None, f"{type(e).__name__}: {e}"
        dt = time.time() - t0
        n_bars = len(body.get("bars") or []) if isinstance(body, dict) else None
        first_t = None
        last_t = None
        if isinstance(body, dict) and body.get("bars"):
            bars = body["bars"]
            first_t = bars[0].get("t") or bars[0].get("ts")
            last_t = bars[-1].get("t") or bars[-1].get("ts")
        row = {
            "market": market, "code": code, "name": name,
            "http_status": status,
            "n_bars": n_bars,
            "first_t": first_t, "last_t": last_t,
            "source": body.get("source") if isinstance(body, dict) else None,
            "backfill": body.get("backfill") if isinstance(body, dict) else None,
            "detail": body.get("detail") if isinstance(body, dict) and status != 200 else None,
            "elapsed_sec": round(dt, 2),
        }
        results.append(row)
        print(f"  {market} {code} {name}: status={status} n_bars={n_bars} "
              f"first={first_t} last={last_t} detail={row['detail']}")
        time.sleep(1.0)  # 遠低於 10秒40次的速率上限，純粹保守間隔
    h1 = health()
    print(f"[結束後] kbars_usage={h1.get('kbars_usage')}")
    out = {
        "probed_at": h1.get("started_at"),
        "kbars_usage_before": h0.get("kbars_usage"),
        "kbars_usage_after": h1.get("kbars_usage"),
        "results": results,
    }
    out_path = Path(__file__).with_name("data") / "probe_kbars_coverage_result.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {out_path}")


if __name__ == "__main__":
    main()
