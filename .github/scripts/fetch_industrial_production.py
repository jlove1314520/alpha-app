# -*- coding: utf-8 -*-
"""每日排程更新 data/industrial_production.json（經濟部統計處工業生產指數）。

`PENDING_QUEUE.md`「源頭二.3」第10名：全體工業生產指數月增/年增，是總經面
常態監控的領先/同時指標（`docs/FIRST_HAND_SOURCES.md` #20）。

資料源（經濟部官方開放資料，`https://data.gov.tw/dataset/6607`）：
`https://service.moea.gov.tw/EE520/opendata/d.csv`（免金鑰，CSV，約8.4MB，
「不定期更新」但實務上每月一次；2026-09-15實測回溯至民國85年1月即
西元1996-01）。

**三來源查證（2026-09-15）**：①`data.gov.tw`資料集#6607頁面（WebSearch找到）
②WebFetch該頁確認CSV下載網址、提供機關（經濟部）、更新頻率③實測`curl`與
Python`requests`皆確認200、內容為合法CSV（`utf-8-sig`編碼），行業代碼`Z`
（行業別標「工業」，不像其他236組代碼有具體行業名稱，判斷為全體工業加總）
逐月序列回溯至1996-01共367筆。

**⚠ 刻意縮小範圍（比照#5借券/#6 13F/#22b內部人交易的既有做法）**：原始
標籤「經濟部工業生產統計與外銷訂單」含兩個子資料集，本輪**只接入工業生產
指數**（單一CSV、單一聚合代碼即可用）；**外銷訂單金額統計未接入**——查證
發現外銷訂單在data.gov.tw是按「產品別」拆成多個獨立資料集（電機產品/
塑橡膠製品等），沒有找到單一「總金額」聚合資料集，需要另一輪查證+加總
邏輯，工作量超出本輪範圍，誠實記錄為已知缺口，非遺漏。

**行業代碼`Z`＝全體工業加總的判斷依據**：CSV裡236組（行業代碼,行業別）
只有`Z`的行業別欄位是不加修飾的「工業」，其餘235組都是具體行業名稱
（例如「食品及飼品製造業」「乳品製造業」），且`Z`在代碼排序上明顯是
非數字的特殊代碼（其餘皆為4位數字），符合官方統計慣例的「總計」代碼。
若未來官方改變代碼配置，本模組會因找不到`Z`而在`errors`誠實記錄，
不會誤用其他代碼硬湊。

**基期**：CSV「計量單位」欄位標明指數基期（目前為「110年=100」，即以
民國110年/西元2021年為基準100），基期會隨官方定期更新而變動，本模組
原樣記錄`base_period`欄位供前端顯示，不自行換算。
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "industrial_production.json"

SOURCE_URL = "https://service.moea.gov.tw/EE520/opendata/d.csv"
SOURCE_LABEL = "經濟部官方開放資料（data.gov.tw #6607，工業生產統計），免金鑰"
TOTAL_INDUSTRY_CODE = "Z"


def _fetch_rows() -> list[dict]:
    resp = requests.get(SOURCE_URL, timeout=60)
    resp.raise_for_status()
    text = resp.content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for raw in reader:
        if raw.get("行業代碼", "").strip() != TOTAL_INDUSTRY_CODE:
            continue
        period = raw.get("資料期(民國年)", "").strip()
        if len(period) != 5:
            continue
        try:
            roc_year = int(period[:3])
            month = int(period[3:])
            value = float(raw["統計值(指數)"])
        except (KeyError, ValueError, TypeError):
            continue
        rows.append({
            "year": roc_year + 1911,
            "month": month,
            "value": value,
            "unit": raw.get("計量單位", ""),
        })
    rows.sort(key=lambda r: (r["year"], r["month"]))
    return rows


def main() -> int:
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SOURCE_LABEL,
        "note": "官方每月更新，資料通常落後1~2個月；僅涵蓋工業生產指數（行業代碼Z=全體工業加總），外銷訂單未接入（已知缺口，見本檔案docstring）",
        "known_gap": "外銷訂單金額統計未接入：官方資料按產品別拆成多個獨立資料集，未找到單一總金額聚合資料集",
        "errors": [],
    }
    try:
        rows = _fetch_rows()
        if not rows:
            raise RuntimeError(f"找不到行業代碼={TOTAL_INDUSTRY_CODE}的任何列，官方代碼配置可能已變更")
        latest = rows[-1]
        payload["latest"] = {
            "date": f"{latest['year']}-{latest['month']:02d}",
            "value": latest["value"],
            "base_period": latest["unit"],
        }
        if len(rows) >= 2:
            prev = rows[-2]
            payload["latest"]["prev_date"] = f"{prev['year']}-{prev['month']:02d}"
            payload["latest"]["change_mom_pct"] = round((latest["value"] / prev["value"] - 1) * 100, 2) if prev["value"] else None
        target_year = latest["year"] - 1
        yoy_row = next((r for r in rows if r["year"] == target_year and r["month"] == latest["month"]), None)
        if yoy_row and yoy_row["value"]:
            payload["yoy_pct"] = round((latest["value"] / yoy_row["value"] - 1) * 100, 2)
            payload["yoy_base_date"] = f"{yoy_row['year']}-{yoy_row['month']:02d}"
        else:
            payload["yoy_pct"] = None
            payload["yoy_base_date"] = None
            payload["errors"].append(f"回傳資料不含{target_year}-{latest['month']:02d}，無法計算YoY")
        payload["history_months"] = len(rows)
        print(f"最新 {payload['latest']['date']}：生產指數{latest['value']}（{latest['unit']}）YoY={payload.get('yoy_pct')}")
    except Exception as e:
        print(f"工業生產指數抓取失敗：{e}")
        payload["errors"].append(f"industrial_production: {e}")
        payload["latest"] = None
        payload["yoy_pct"] = None

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}")
    return 0 if payload.get("latest") else 1


if __name__ == "__main__":
    raise SystemExit(main())
