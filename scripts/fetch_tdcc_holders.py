# -*- coding: utf-8 -*-
"""千張大戶／集保股權分散表（源頭一.2a，2026-09-10）。

規格見 `PENDING_QUEUE.md`「源頭一：籌碼K線功能全拆解」總司令原話 2(a)：
> 千張大戶：集保 opendata.tdcc.com.tw/getOD.ashx?id=1-5，每週五 20:00 抓一次，
> 存 research/data/tdcc/ 累積，產 data/holders.json（≥1000張比例、≤1張比例、
> 週變化、連續增減週數）。

資料來源：台灣集中保管結算所（TDCC）「集保股權分散表」公開資料，
免金鑰、免驗證碼，端點 https://opendata.tdcc.com.tw/getOD.ashx?id=1-5。
這是官方每週更新一次的**全市場最新快照**（不是時間序列 API，每次呼叫只拿得到
「目前最新一週」的資料），所以要靠**每週呼叫一次＋本機累積**自己組出時間序列，
過去的週別無法回補（TDCC 沒有提供歷史查詢端點，2026-09-10 僅查了這一個端點，
其官方首頁 https://opendata.tdcc.com.tw/ 亦未列出歷史版本查詢功能）。

CSV 欄位：資料日期,證券代號,持股分級,人數,股數,占集保庫存數比例%
持股分級（TDCC 標準 17 級距，股數單位）：
  1 = 1~999（不足 1 張，本規格「≤1張比例」）
  2~14 = 中間級距
  15 = 1,000,001 以上（本規格「≥1000張比例」，業界慣稱「千張大戶」）
  16 = 差異數調整（通常為 0，非實際持股級距）
  17 = 合計（占比恆為 100.00，用來做資料完整性檢查）

**已知限制（誠實揭露，不得省略）**：
1. 只能「往前累積」，無法回補歷史——第一次執行後至少要等第二次（下一週）
   才有「週變化」，等連續多週才有「連續增減週數」，第一週一律是 null。
2. 級距以股數分界，1,000,001 股≈1000.001 張，與「整數 1000 張」略有一股之差，
   這是 TDCC 官方級距本身的定義，不是本腳本的誤差。
3. 呼叫時間點（週五 20:00）不保證 TDCC 當週已更新——若當週尚未發布，
   會抓到與上週相同的「資料日期」，這種情況下腳本會偵測到重複日期並跳過寫入
   （見 `_save_snapshot`），不會製造假的「兩週都一樣」假象。
"""
from __future__ import annotations

import csv
import io
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
TDCC_DIR = ROOT / "research" / "data" / "tdcc"
OUT = ROOT / "data" / "holders.json"
TZ = timezone(timedelta(hours=8))

URL = "https://opendata.tdcc.com.tw/getOD.ashx?id=1-5"
EXPECTED_HEADER = "資料日期,證券代號,持股分級,人數,股數,占集保庫存數比例%"

LEVEL_SMALL = "1"    # <=1張（1~999股）
LEVEL_BIG = "15"      # >=1000張（1,000,001股以上）
LEVEL_TOTAL = "17"    # 合計，用來做完整性檢查


def _load(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def fetch_raw() -> str | None:
    """打官方端點，回傳原始 CSV 文字；驗不過就回傳 None（不猜、不產生假資料）。"""
    try:
        resp = requests.get(
            URL, timeout=30,
            headers={"User-Agent": "AlphaApp-research/1.0 (holders.json weekly fetch)"},
        )
    except requests.RequestException as e:
        print(f"! 連線失敗：{type(e).__name__}: {e}")
        return None
    if resp.status_code != 200:
        print(f"! HTTP {resp.status_code}，非預期")
        return None
    text = resp.content.decode("utf-8-sig", errors="replace")
    first_line = text.splitlines()[0].strip() if text else ""
    # 已知地雷同款檢查（CLAUDE.md）：不能只看狀態碼，200 也可能是 HTML 錯誤頁。
    if first_line != EXPECTED_HEADER:
        print(f"! 回應格式不符預期（首行：{first_line[:80]!r}），視為失敗，不寫入")
        return None
    return text


def _save_snapshot(text: str) -> str | None:
    """存進 research/data/tdcc/，回傳本次資料日期（存了新檔或本來就有才回傳；否則 None）。"""
    reader = csv.reader(io.StringIO(text))
    next(reader)  # 跳過表頭
    dates = defaultdict(int)
    for row in reader:
        if len(row) < 6:
            continue
        dates[row[0].strip()] += 1
    if not dates:
        print("! CSV 沒有資料列，不寫入")
        return None
    report_date = max(dates, key=dates.get)
    if len(dates) > 1:
        print(f"! 警告：單次回應內含多個資料日期 {dict(dates)}，取列數最多的 {report_date} 為準")

    TDCC_DIR.mkdir(parents=True, exist_ok=True)
    dest = TDCC_DIR / f"{report_date}.csv"
    if dest.exists():
        print(f"  {report_date} 已有存檔（{dest.name}），本次不覆寫，視為「TDCC 尚未更新到新一週」")
        return report_date
    dest.write_text(text, encoding="utf-8")
    print(f"  已存新快照：{dest.name}（{sum(dates.values())} 列）")
    return report_date


def _parse_snapshot(path: Path) -> dict[str, dict]:
    """解析單一週快照，只留 level 1/15/17 三格（其餘不需要，省記憶體）。"""
    out: dict[str, dict] = {}
    text = path.read_text(encoding="utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    next(reader, None)
    for row in reader:
        if len(row) < 6:
            continue
        _date, code, level, holders, shares, ratio = (c.strip() for c in row[:6])
        code = code.strip()
        if level not in (LEVEL_SMALL, LEVEL_BIG, LEVEL_TOTAL):
            continue
        try:
            entry = out.setdefault(code, {})
            entry[level] = {
                "holders": int(holders),
                "shares": int(shares),
                "ratio": float(ratio),
            }
        except ValueError:
            continue
    return out


def _streak(diffs: list[float]) -> int:
    """連續同向週數：正=連漲、負=連跌、0=最新一週持平或資料不足。"""
    if not diffs:
        return 0
    sign = 1 if diffs[-1] > 0 else (-1 if diffs[-1] < 0 else 0)
    if sign == 0:
        return 0
    n = 0
    for v in reversed(diffs):
        if (v > 0 and sign > 0) or (v < 0 and sign < 0):
            n += 1
        else:
            break
    return n * sign


def build_holders_json() -> int:
    snapshot_files = sorted(TDCC_DIR.glob("*.csv"))
    if not snapshot_files:
        print("! research/data/tdcc/ 底下沒有任何快照，無法產生 holders.json")
        return 1

    per_date: dict[str, dict[str, dict]] = {}
    for f in snapshot_files:
        date = f.stem
        per_date[date] = _parse_snapshot(f)
    dates = sorted(per_date.keys())
    print(f"累積 {len(dates)} 週快照：{dates[0]} ~ {dates[-1]}")

    company_info = (_load(ROOT / "data" / "company_info.json", {}) or {}).get("companies") or {}
    active = set((_load(ROOT / "data" / "listed_universe.json", {}) or {}).get("active") or [])

    codes = set()
    for d in dates:
        codes.update(per_date[d].keys())

    integrity_bad = 0
    stocks_out: dict[str, dict] = {}
    for code in sorted(codes):
        history = []
        for d in dates:
            rec = per_date[d].get(code)
            if not rec or LEVEL_BIG not in rec or LEVEL_SMALL not in rec or LEVEL_TOTAL not in rec:
                continue
            total = rec[LEVEL_TOTAL]
            # 完整性檢查：合計列占比理論上恆為 100.00，偏離代表這筆資料本身有問題。
            if abs(total["ratio"] - 100.0) > 0.5:
                integrity_bad += 1
                continue
            history.append({
                "date": d,
                "big_holder_ratio": rec[LEVEL_BIG]["ratio"],
                "big_holder_count": rec[LEVEL_BIG]["holders"],
                "small_holder_ratio": rec[LEVEL_SMALL]["ratio"],
                "small_holder_count": rec[LEVEL_SMALL]["holders"],
                "total_holders": total["holders"],
                "total_shares": total["shares"],
            })
        if not history:
            continue

        latest = history[-1]
        big_ratios = [h["big_holder_ratio"] for h in history]
        diffs = [round(b - a, 4) for a, b in zip(big_ratios, big_ratios[1:])]

        entry = {
            "name": (company_info.get(code) or {}).get("name"),
            "in_universe": code in active,
            "date": latest["date"],
            "big_holder_ratio": latest["big_holder_ratio"],
            "big_holder_count": latest["big_holder_count"],
            "small_holder_ratio": latest["small_holder_ratio"],
            "small_holder_count": latest["small_holder_count"],
            "total_holders": latest["total_holders"],
            "total_shares": latest["total_shares"],
            "week_change_pct": round(diffs[-1], 2) if diffs else None,
            "streak_weeks": _streak(diffs),
            "weeks_available": len(history),
            # 只留最近 12 週明細，避免檔案隨時間無限膨脹
            "history": history[-12:],
        }
        stocks_out[code] = entry

    if integrity_bad:
        print(f"  完整性檢查：{integrity_bad} 筆（週,股票）合計列占比偏離 100%，已排除")

    doc = {
        "meta": {
            "generated_at": datetime.now(TZ).isoformat(),
            "source": "TDCC 集保結算所 集保股權分散表（官方免費，免金鑰，getOD.ashx?id=1-5）",
            "url": URL,
            "update_cadence": "官方每週更新一次；本管線排程於每週五 20:00 呼叫一次",
            "weeks_accumulated": len(dates),
            "dates_available": dates,
            "big_holder_definition": "持股分級 15 級（1,000,001股以上，業界慣稱「千張大戶」，"
                                       "占集保庫存數比例%）",
            "small_holder_definition": "持股分級 1 級（1~999股，不足 1 張）",
            "known_gaps": [
                "TDCC 未提供歷史查詢端點，只能往前累積，無法回補過去週別"
                "（2026-09-10 查證：官方端點文件與 opendata.tdcc.com.tw 首頁均未列出歷史版本查詢功能）",
                "第一週沒有週變化與連續增減週數（history 不足 2 筆時皆為 null/0）",
                "呼叫時間（週五 20:00）不保證 TDCC 當週已發布新資料，"
                "若偵測到與既有檔案同一資料日期，本次不會重複寫入或誤植假週別",
            ],
            "integrity_check_failed_rows": integrity_bad,
        },
        "stocks": stocks_out,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"holders.json：{len(stocks_out)} 檔　→ {OUT.relative_to(ROOT)}"
          f"（{OUT.stat().st_size / 1e6:.2f}MB）")
    return 0


def main() -> int:
    text = fetch_raw()
    if text is None:
        print("本次抓取失敗，改用既有累積快照重建 holders.json（若有的話）")
    else:
        _save_snapshot(text)
    return build_holders_json()


if __name__ == "__main__":
    sys.exit(main())
