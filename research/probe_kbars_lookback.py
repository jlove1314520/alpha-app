"""分K.零 探針（第2子問題）：api.kbars() 最多能回溯多久。

前提：`shioaji_quotes.py`/`alpha_live_server.py` 已擴充 op="kbars" 協定支援
可選的 start/end（2026-09-29），新增 `/live/kbars_probe?code=&start=&end=`
端點，沿用既有Shioaji連線、不開第二條、走既有240次/日預算。只回筆數＋首尾
時間（不回完整bars），避免多年區間資料量塞爆通道。

用法：python research/probe_kbars_lookback.py

方法：對每個檔位測試一組往回遞增的錨點日期，每個錨點用「錨點±7天」的窗口
（吃掉週末/假日造成的假陰性——若窗口內完全沒有交易日,才會誤判成「沒資料」，
7天窗口保證至少涵蓋約5個交易日）。找到第一個「有資料」與「無資料」的邊界，
就是實測回溯上限的量級（不是精確到天，量級足以判斷分K.一/二/三要開哪些）。
"""
import json
import time
from datetime import date, timedelta
from pathlib import Path

import requests

TOKEN = Path(__file__).with_name(".alpha_live_token").read_text(encoding="utf-8").strip()
BASE = "http://127.0.0.1:8001"
HEADERS = {"X-Alpha-Local-Token": TOKEN}

TODAY = date.today()

# 錨點：距今天多少天，由近到遠。先用主標的（2330，最長上市歷史）掃過一輪
# 找邊界量級，再用少量錨點測第二個標的（0050，ETF）確認涵蓋類型是否一致。
ANCHORS_DAYS_MAIN = [30, 180, 365, 365 * 2, 365 * 3, 365 * 5, 365 * 8, 365 * 12, 365 * 20]
ANCHORS_DAYS_SECOND = [365, 365 * 3, 365 * 5]

MAIN_CODE = ("2330", "台積電")
SECOND_CODE = ("0050", "元大台灣50")

WINDOW_DAYS = 7  # 錨點左右各7天，吃掉週末/假日


def health():
    r = requests.get(f"{BASE}/health", headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()


def probe(code: str, anchor_days_ago: int):
    anchor = TODAY - timedelta(days=anchor_days_ago)
    start = (anchor - timedelta(days=WINDOW_DAYS)).isoformat()
    end = (anchor + timedelta(days=WINDOW_DAYS)).isoformat()
    t0 = time.time()
    try:
        r = requests.get(f"{BASE}/live/kbars_probe",
                          params={"code": code, "start": start, "end": end},
                          headers=HEADERS, timeout=20)
        status = r.status_code
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
    except Exception as e:  # noqa: BLE001 — 探針腳本，單筆失敗不能拖垮其他筆
        status, body = None, f"{type(e).__name__}: {e}"
    dt = time.time() - t0
    return {
        "anchor_days_ago": anchor_days_ago,
        "anchor_date": anchor.isoformat(),
        "window": [start, end],
        "status": status,
        "elapsed_sec": round(dt, 2),
        "n_bars": body.get("bar_count") if isinstance(body, dict) else None,
        "first_bar_t": body.get("first_bar_t") if isinstance(body, dict) else None,
        "last_bar_t": body.get("last_bar_t") if isinstance(body, dict) else None,
        "error": body.get("error") if isinstance(body, dict) else None,
        "raw": body if not isinstance(body, dict) else None,
    }


def main():
    h0 = health()
    print(f"[開始前] kbars_usage={h0.get('kbars_usage')}, shioaji_connected={h0.get('shioaji_connected')}")

    results = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
               "kbars_usage_before": h0.get("kbars_usage"),
               "main": {"code": MAIN_CODE[0], "name": MAIN_CODE[1], "probes": []},
               "second": {"code": SECOND_CODE[0], "name": SECOND_CODE[1], "probes": []}}

    print(f"\n=== 主標的 {MAIN_CODE[1]}({MAIN_CODE[0]}) ===")
    for d in ANCHORS_DAYS_MAIN:
        res = probe(MAIN_CODE[0], d)
        results["main"]["probes"].append(res)
        print(f"  錨點{d:>5}天前（{res['anchor_date']}）：status={res['status']} "
              f"n_bars={res['n_bars']} first={res['first_bar_t']} last={res['last_bar_t']} error={res['error']}")
        time.sleep(0.5)

    print(f"\n=== 次標的 {SECOND_CODE[1]}({SECOND_CODE[0]}) ===")
    for d in ANCHORS_DAYS_SECOND:
        res = probe(SECOND_CODE[0], d)
        results["second"]["probes"].append(res)
        print(f"  錨點{d:>5}天前（{res['anchor_date']}）：status={res['status']} "
              f"n_bars={res['n_bars']} first={res['first_bar_t']} last={res['last_bar_t']} error={res['error']}")
        time.sleep(0.5)

    h1 = health()
    results["kbars_usage_after"] = h1.get("kbars_usage")
    print(f"\n[結束後] kbars_usage={h1.get('kbars_usage')}")

    out_path = Path(__file__).with_name("data") / "probe_kbars_lookback_result.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n結果已寫入 {out_path}")


if __name__ == "__main__":
    main()
