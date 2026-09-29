"""分K.零 探針（第3子問題）：停牌（零成交）與漲跌停鎖住當天，api.kbars() 的表現。

前提：`shioaji_quotes.py` 已擴充 op="kbars" 協定支援可選 start/end
（2026-09-29，見 probe_kbars_lookback.py 的說明），`/live/kbars_probe`
端點沿用既有Shioaji連線、不開第二條。

**離峰時段測試（2026-09-29第665輪新增）**：本探針需要在非交易時段執行時，
先用 `ALPHA_SHIOAJI_FORCE_RUN=1` 啟動 `shioaji_quotes.py`（2026-09-06
實測.二.1既有設計，專為這種端到端驗證需求開的開關，非新增機制）；
不設此環境變數時常駐行程在非交易時段會走快速路徑直接結束、不開kbars服務。
測完要手動 `taskkill` 關閉這個強制啟動的行程，讓排程下一輪（每2分鐘）
偵測到PID檔陳舊後自然接手，恢復正常「非交易時段=快速路徑」行為。

候選日期怎麼選：掃描 `data/price_history.json`（90天OHLCV快取）找
(a) 收盤鎖在漲跌停（high==low==close 且與前一日close差±9.3%~10.3%）
(b) 當天volume==0（前後一天皆正常交易，排除新掛牌/已下市造成的邊界0）
這兩類各取幾個真實案例，見 PENDING_QUEUE.md「分K.零」條目挑選過程。

用法：python research/probe_kbars_halted_days.py
"""
import json
import time
from pathlib import Path

import requests

TOKEN = Path(__file__).with_name(".alpha_live_token").read_text(encoding="utf-8").strip()
BASE = "http://127.0.0.1:8001"
HEADERS = {"X-Alpha-Local-Token": TOKEN}

# 案例來源：掃描 data/price_history.json 找到的真實紀錄（2026-09-29第665輪）。
CASES = [
    ("限跌鎖住", "1310", "2026-07-28"),
    ("限跌鎖住", "2464", "2026-06-08"),
    ("限漲鎖住", "1312", "2026-08-27"),
    ("限漲鎖住", "1303", "2026-07-31"),
    ("停牌(零成交)", "1218", "2026-08-13"),
    ("停牌(零成交)", "1788", "2026-06-18"),
]


def kbars_probe(code: str, d: str):
    r = requests.get(f"{BASE}/live/kbars_probe", params={"code": code, "start": d, "end": d},
                      headers=HEADERS, timeout=20)
    return r.status_code, r.json()


def main():
    results = []
    for label, code, d in CASES:
        try:
            status, body = kbars_probe(code, d)
        except Exception as e:  # noqa: BLE001 — 探針腳本，單筆失敗不能拖垮其他筆
            status, body = None, {"error": f"{type(e).__name__}: {e}"}
        print(f"{label} {code} {d} -> status={status} {body}")
        results.append({"label": label, "code": code, "date": d, "http_status": status, "result": body})
        time.sleep(1.0)

    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"), "cases": results}
    out_path = Path(__file__).with_name("data") / "probe_kbars_halted_days_result.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"寫入 {out_path}")


if __name__ == "__main__":
    main()
