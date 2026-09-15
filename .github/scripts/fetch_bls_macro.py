# -*- coding: utf-8 -*-
"""每日排程更新 data/bls_macro.json（美國勞工統計局總經指標）。

`PENDING_QUEUE.md`「源頭二.3」第8名：美國失業率、CPI年增率、非農就業人數，
是專業投資人常態監控的核心總經指標（`docs/FIRST_HAND_SOURCES.md` #25）。

資料源（BLS Public Data API v2，未註冊金鑰即可用，`https://www.bls.gov/
developers/api_signature_v2.htm`）：
`https://api.bls.gov/publicAPI/v2/timeseries/data/{series_id}`（GET，免金鑰）。

**三來源查證（2026-09-15）**：①BLS官方API文件
`https://www.bls.gov/developers/api_signature_v2.htm`（WebFetch確認v1/v2差異、
免金鑰可用、JSON回應結構）②WebSearch多篇第三方API整合文件交叉確認「無金鑰
25次/日、註冊後500次/日、v1/v2皆支援GET」③實測：`curl`三個series id
（`LNS14000000`失業率／`CUUR0000SA0`CPI-U／`CES0000000001`非農就業人數）
皆回`REQUEST_SUCCEEDED`、200、合法JSON，未註冊金鑰即成功，回溯約32個月
（2024-01~2026-08），足夠計算YoY。

**免金鑰限制**：官方文件未明講未註冊時的每日次數上限，第三方文件普遍引用
「25次/日」（相對於註冊後500次/日）；本管線每日僅呼叫3次（三個series各一次），
遠低於此上限，故未申請`BLS_API_KEY`、未加GitHub Secrets（若未來要擴充更多
series，需重新評估是否申請金鑰，屬於「需要總司令裁示是否申請」的範疇，
非本輪判斷）。

**CPI年增率算法**：BLS API回傳的是CPI指數本身（非年增率），本管線自行計算：
取最新月份指數 ÷ 12個月前同月指數 － 1；若拿不到12個月前的資料則該欄位為
null並記錄原因（不得用近似月份湊數，例如缺8月用9月頂替）。

**非農就業人數**：`CES0000000001`為千人為單位的總非農就業人數水準（不含
農業），本管線同時提供最新值與月增（MoM，千人）；不做年增率（該序列各月
波動大，年增率不是財經媒體常用口徑，MoM才是「新增就業」的標準說法）。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "bls_macro.json"

BASE_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/{series_id}"
HEADERS = {"User-Agent": "AlphaApp-BlsMacro contact@alpha-app-project.example"}
REQUEST_SLEEP_SEC = 0.5

SERIES = {
    "unemployment_rate": {"id": "LNS14000000", "name": "失業率（Unemployment Rate）", "unit": "%"},
    "cpi_u": {"id": "CUUR0000SA0", "name": "CPI-U 全項消費者物價指數", "unit": "index"},
    "nonfarm_payrolls": {"id": "CES0000000001", "name": "非農就業人數（All Employees, Total Nonfarm）", "unit": "thousands"},
}


def _period_key(row: dict) -> tuple[int, int]:
    return (int(row["year"]), int(row["period"][1:]))


def fetch_series(series_id: str) -> list[dict]:
    url = BASE_URL.format(series_id=series_id)
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    body = r.json()
    if body.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS回應status非成功：{body.get('status')}，message={body.get('message')}")
    series = body.get("Results", {}).get("series", [])
    if not series:
        raise RuntimeError("BLS回應無series資料")
    rows = [row for row in series[0].get("data", []) if row.get("period", "").startswith("M") and row["period"] != "M13"]
    rows.sort(key=_period_key)
    return rows


def main() -> int:
    out_series: dict[str, dict] = {}
    errors: list[dict] = []

    for key, info in SERIES.items():
        time.sleep(REQUEST_SLEEP_SEC)
        try:
            rows = fetch_series(info["id"])
        except Exception as e:
            errors.append({"series": key, "reason": str(e)})
            print(f"  ・{key}: 抓取失敗 {e}")
            continue
        clean = []
        for row in rows:
            try:
                val = float(row["value"])
            except (ValueError, TypeError):
                continue
            clean.append({
                "date": f"{row['year']}-{row['period'][1:]}",
                "value": val,
                "period_name": row.get("periodName"),
            })
        if not clean:
            errors.append({"series": key, "reason": "查無可解析的數值列"})
            print(f"  ・{key}: 查無可解析數值")
            continue

        latest = clean[-1]
        entry = {
            "name": info["name"],
            "unit": info["unit"],
            "series_id": info["id"],
            "latest_date": latest["date"],
            "latest_value": latest["value"],
        }
        if key == "cpi_u":
            # YoY：找同月上一年那一筆，缺就誠實記 null，不用鄰近月份湊數
            target_year = int(latest["date"][:4]) - 1
            target_month = latest["date"][5:7]
            yoy_row = next((c for c in clean if c["date"] == f"{target_year}-{target_month}"), None)
            if yoy_row and yoy_row["value"]:
                entry["yoy_pct"] = round((latest["value"] / yoy_row["value"] - 1) * 100, 2)
                entry["yoy_base_date"] = yoy_row["date"]
            else:
                entry["yoy_pct"] = None
                entry["yoy_base_date"] = None
                errors.append({"series": key, "reason": f"回傳資料不含{target_year}-{target_month}，無法計算YoY"})
        if key in ("unemployment_rate", "nonfarm_payrolls") and len(clean) >= 2:
            prev = clean[-2]
            entry["prev_date"] = prev["date"]
            entry["prev_value"] = prev["value"]
            entry["change_mom"] = round(latest["value"] - prev["value"], 3)

        out_series[key] = entry
        print(f"  ・{key}: 最新 {latest['date']} = {latest['value']}")

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "BLS官方Public Data API v2（未註冊金鑰，https://api.bls.gov/publicAPI/v2/timeseries/data/）",
        "note": "失業率/非農就業人數為官方月頻統計常有一個月落後；CPI年增率為本管線自行計算（最新月指數÷12個月前同月指數-1），非BLS原始欄位；僅供參考非投資建議",
        "errors": errors,
        "series": out_series,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"寫入 {OUT_PATH}，{len(out_series)} 個序列" + (f"，{len(errors)}筆錯誤" if errors else ""))
    return 0 if out_series else 1


if __name__ == "__main__":
    raise SystemExit(main())
