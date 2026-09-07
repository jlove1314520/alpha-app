# -*- coding: utf-8 -*-
"""產業金流地圖聚合（金流一.1，2026-09-08）。

規格見 `PENDING_QUEUE.md`「金流一：產業金流地圖」總司令原話。

**零額外請求**：只讀 repo 內既有檔案
（`data/institutional_history.json`、`price_history.json`、
`company_info.json`、`listed_universe.json`），不對 TWSE/TPEx 打任何一次。

**誠實原則（這支腳本最重要的部分）**

規格要 5／20／60 日視窗。今天只有 9 個交易日的法人歷史，原因寫在
`accumulate_institutional.py` 的 docstring：近 60 日的 T86 整段落在
holdout `(VAL_END=2024-12-31, today]`，回補等於解鎖 holdout，需總司令明確同意。

所以這支腳本**只輸出當下算得出來的視窗**，算不出來的：
- **不補零、不外插、不用短視窗冒充長視窗**
- 在 `windows_missing_days` 寫明還缺幾個交易日
- 前端據此顯示「累積中」而不是一個假數字

**已知缺口（不得靜默忽略）**

1. **自營商無法排除避險**：規格要「只算自行買賣，排除避險」，但
   `stock_detail.json` 的 `dealer_lots` 是**合併值**，T86 原始的
   「自行買賣／避險」兩欄在既有管線就已經被加總掉了。
   本版標 `dealer_lots_includes_hedge: true`，要拆分必須改上游
   `fetch_market_tw.py` 的 T86 解析——另案。
2. **金額一律是估算**：`est_amount = 張數 × 1000 × 當日收盤`，
   不是真實成交金額（法人可能在盤中任何價位成交）。欄位名帶 `est_` 前綴。
3. **上櫃產業別**：`company_info.json` 的 industry 已含上櫃，
   規格提的 `t187ap03_O` 回補屬金流一.2，未做。
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
OUT = D / "sector_flow.json"
TZ = timezone(timedelta(hours=8))

# 1 日＝規格的「當日」切換；5/20/60 是規格指定的三個視窗。
# 1 日一定算得出來（只要有一天資料），所以放進來不會有「假裝有」的問題。
WINDOWS = (1, 5, 20, 60)
ZSCORE_WINDOW = 60
ZSCORE_THRESHOLD = 2.0     # 寫死門檻，規格指定 |z|>=2 才亮

# 規格：「ETF、權證、DR 不得混進產業合計」。這些在 company_info 的 industry
# 欄位裡長得跟真產業一模一樣（"ETF" 268 檔、"上櫃ETF" 122 檔、"存託憑證" 36 檔…），
# 不排除的話它們會變成榜上最大的「產業」——實測第一版就是 ETF 淨流出 -363,316 張
# 排在流出第一名，那不是一個產業的金流，是一堆追蹤大盤的工具。
NON_INDUSTRY = {
    "ETF", "上櫃ETF", "ETN", "存託憑證", "受益證券",
    "上櫃指數股票型基金(ETF)", "指數投資證券(ETN)",
}


def _is_industry(name) -> bool:
    """真產業才算。名稱含 ETF/ETN/存託/受益 一律排除，避免日後新增類別漏接。"""
    if not name or name in NON_INDUSTRY:
        return False
    return not any(t in str(name) for t in ("ETF", "ETN", "存託", "受益"))


# 一個日期要算「這天有全市場資料」，至少要有最大覆蓋檔數的這個比例。
# 為什麼需要這道過濾（實測踩到的）：累積器是從各檔 stock_detail 的 history 收來的，
# 不同股票帶回來的歷史長度不一樣，於是日期軸會被少數股票拉長——
# 實測 9 個日期裡，20260901~20260907 這 5 天每天約 1,860~2,008 檔，
# 但 20260826 只有 **4 檔**、20260827 只有 38 檔。
# 那 4 天不是「全市場那天的資料」，是零星殘留。
# 不濾掉的話會有兩個後果：(1) 檔案宣稱「9 個交易日」是**高估**；
# (2) 「20 日視窗還需 11 天」的倒數跟著樂觀，實際還需 15 天。
# 對使用者而言，一個樂觀的倒數比沒有倒數更糟——他會以為快好了。
MIN_DATE_COVERAGE = 0.5


def _solid_dates(dates: list, series: dict) -> list:
    """只留「該日有足夠橫斷面覆蓋」的日期。"""
    counts = {d: sum(1 for b in series.values() if d in b) for d in dates}
    if not counts:
        return []
    peak = max(counts.values())
    keep = [d for d in dates if counts[d] >= peak * MIN_DATE_COVERAGE]
    dropped = [(d, counts[d]) for d in dates if d not in keep]
    if dropped:
        print("  剔除覆蓋不足的日期（非全市場資料，只是零星殘留）：")
        for d, n in dropped:
            print(f"    {d}: 只有 {n} 檔（門檻 {peak * MIN_DATE_COVERAGE:.0f} 檔）")
    return keep


def _load(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _closes(price_history: dict) -> dict:
    """每檔最新收盤價，供估算金額用。"""
    out = {}
    for code, rows in (price_history.get("prices") or {}).items():
        if rows:
            c = rows[-1].get("close")
            if isinstance(c, (int, float)):
                out[code] = float(c)
    return out


def _streak(vals: list) -> int:
    """連續同向天數：正=連買、負=連賣、0=最新一天持平或無資料。

    由最新往回數，方向一變就停。
    """
    if not vals:
        return 0
    sign = 1 if vals[-1] > 0 else (-1 if vals[-1] < 0 else 0)
    if sign == 0:
        return 0
    n = 0
    for v in reversed(vals):
        if (v > 0 and sign > 0) or (v < 0 and sign < 0):
            n += 1
        else:
            break
    return n * sign


def main() -> int:
    hist = _load(D / "institutional_history.json")
    if not hist or not hist.get("dates"):
        print("! 沒有 data/institutional_history.json，"
              "先跑 .github/scripts/accumulate_institutional.py")
        return 1
    series = hist["series"]
    dates = _solid_dates(hist["dates"], series)
    if not dates:
        print("! 沒有任何日期達到覆蓋門檻，不寫出檔案")
        return 1
    n_dates = len(dates)

    ci = _load(D / "company_info.json", {}) or {}
    companies = ci.get("companies") or {}
    uni = _load(D / "listed_universe.json", {}) or {}
    active = set(uni.get("active") or [])
    closes = _closes(_load(D / "price_history.json", {}) or {})

    usable = [w for w in WINDOWS if n_dates >= w]
    missing = {str(w): w - n_dates for w in WINDOWS if n_dates < w}
    print(f"法人歷史 {n_dates} 個交易日（{dates[0]}~{dates[-1]}），"
          f"可用視窗 {usable if usable else '無'}")
    if not usable:
        print("! 連最短的 5 日視窗都不足，不寫出檔案（避免產生一份空殼讓前端誤以為有資料）")
        return 1

    stocks_out = {}
    for code, bucket in series.items():
        if code not in active:
            continue
        # 對齊到全體日期軸；某天缺資料視為「當天無法人進出」，但記錄 days_present
        f_ser, t_ser, d_ser, present = [], [], [], 0
        for d in dates:
            r = bucket.get(d)
            if r is None:
                f_ser.append(0.0)
                t_ser.append(0.0)
                d_ser.append(0.0)
            else:
                present += 1
                f_ser.append(float(r[0] or 0))
                t_ser.append(float(r[1] or 0))
                d_ser.append(float(r[2] or 0))
        total_ser = [a + b + c for a, b, c in zip(f_ser, t_ser, d_ser)]
        close = closes.get(code)

        entry = {
            "industry": (companies.get(code) or {}).get("industry"),
            "days_present": present,
            "close": close,
            "dealer_lots_includes_hedge": True,   # 已知缺口 1
        }
        for w in usable:
            fw = sum(f_ser[-w:])
            tw = sum(t_ser[-w:])
            dw = sum(d_ser[-w:])
            allw = sum(total_ser[-w:])
            entry[f"net_{w}d"] = {
                "foreign_lots": round(fw, 1),
                "trust_lots": round(tw, 1),
                "dealer_lots": round(dw, 1),
                "total_lots": round(allw, 1),
                # 估算：張×1000×收盤。不是真實成交金額，故欄位名帶 est_
                "est_amount": round(allw * 1000 * close) if close else None,
            }
        entry["streak_days"] = {
            "foreign": _streak(f_ser),
            "trust": _streak(t_ser),
            "total": _streak(total_ser),
        }
        w0 = usable[0]
        fs, ts = sum(f_ser[-w0:]), sum(t_ser[-w0:])
        entry["foreign_trust_aligned"] = bool((fs > 0 and ts > 0) or (fs < 0 and ts < 0))

        # 異常大買/大賣 z 分數：資料不足就**不給**，不降級用短視窗冒充
        if n_dates >= ZSCORE_WINDOW and close:
            amts = [v * 1000 * close for v in total_ser[-ZSCORE_WINDOW:]]
            sd = statistics.pstdev(amts)
            if sd > 0:
                z = (amts[-1] - statistics.fmean(amts)) / sd
                entry["z_today"] = round(z, 2)
                entry["abnormal"] = abs(z) >= ZSCORE_THRESHOLD
        stocks_out[code] = entry

    # ── 產業層 ────────────────────────────────────────────────────────────
    w_main = 5 if 5 in usable else usable[0]
    by_ind = defaultdict(list)
    excluded_non_industry = 0
    for code, e in stocks_out.items():
        ind = e.get("industry")
        if not ind:
            continue
        if not _is_industry(ind):
            excluded_non_industry += 1
            continue
        by_ind[ind].append(code)
    print(f"  排除非產業類別（ETF／ETN／DR／受益證券）：{excluded_non_industry} 檔")

    sectors = {}
    for ind, codes in by_ind.items():
        agg = {"constituents": len(codes)}
        for w in usable:
            agg[f"net_{w}d_lots"] = round(
                sum((stocks_out[c].get(f"net_{w}d") or {}).get("total_lots") or 0
                    for c in codes), 1)
            agg[f"net_{w}d_est_amount"] = sum(
                (stocks_out[c].get(f"net_{w}d") or {}).get("est_amount") or 0
                for c in codes)
        # 加速度要同時有 5 與 20 日，缺一不算——不用別的視窗頂替
        if 5 in usable and 20 in usable:
            d5 = agg["net_5d_lots"] / 5
            d20 = agg["net_20d_lots"] / 20
            agg["acceleration"] = round(d5 - d20, 2)
            agg["quadrant"] = (("流入加速" if d5 > d20 else "流入放緩") if d5 > 0
                               else ("流出放緩" if d5 > d20 else "流出加速"))
        # 2026-09-08 排序依「估算金額」不是張數——這是實測截圖抓到的不一致：
        # 半導體業標題 +415.7 億，成分股卻依張數排，聯電 26,202 張排第一，
        # 而真正撐起那 415 億的台積電（2,440 元一張）只排第四。
        # 標題講金額、清單講張數，兩者對「誰重要」的答案不一樣，那是誤導。
        ranked = sorted(
            codes,
            key=lambda c: (stocks_out[c].get(f"net_{w_main}d") or {}).get("est_amount") or 0)

        def _row(c):
            return {"code": c,
                    "name": (companies.get(c) or {}).get("name"),
                    "lots": (stocks_out[c].get(f"net_{w_main}d") or {}).get("total_lots"),
                    "est_amount": (stocks_out[c].get(f"net_{w_main}d") or {}).get("est_amount")}

        agg["rank_window_days"] = w_main
        agg["top_inflow"] = [_row(c) for c in ranked[::-1][:10]]
        agg["top_outflow"] = [_row(c) for c in ranked[:10]]
        sectors[ind] = agg

    doc = {
        "meta": {
            "generated_at": datetime.now(TZ).isoformat(),
            "date": dates[-1],
            "trading_days_available": n_dates,
            "dates_dropped_low_coverage": len(hist["dates"]) - n_dates,
            "date_coverage_rule": f"只採計橫斷面覆蓋 >= 尖峰 {MIN_DATE_COVERAGE:.0%} 的日期",
            "windows_usable": usable,
            "windows_missing_days": missing,
            "zscore_window": ZSCORE_WINDOW,
            "zscore_threshold": ZSCORE_THRESHOLD,
            "disclaimer": "法人行為（描述性資訊，非預測訊號）",
            "non_industry_excluded": excluded_non_industry,
            "known_gaps": [
                "張數與金額可能反向：淨張數為負而淨金額為正是合理的"
                "（貴的被買、便宜的被賣），前端應以金額為主、張數為輔",
                "自營商為合併值，未排除避險（上游 fetch_market_tw.py 的 T86 解析已加總）",
                "est_amount = 張數×1000×當日收盤，為估算非真實成交金額",
                "上櫃產業別沿用 company_info，未接 t187ap03_O（金流一.2）",
            ],
            "why_windows_incomplete":
                "法人歷史採往前累積（零額外請求）。近 60 交易日 T86 落在 holdout "
                "(VAL_END=2024-12-31, today]，回補等於解鎖 holdout，需總司令明確同意，故不做。",
            "source": "data/institutional_history.json（每日管線既有呼叫，零額外請求）",
        },
        "sectors": sectors,
        "stocks": stocks_out,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    print(f"sector_flow.json：{len(stocks_out)} 檔、{len(sectors)} 個產業，"
          f"{OUT.stat().st_size / 1e6:.1f}MB")
    if missing:
        print("  尚缺：" + "、".join(f"{w} 日視窗還差 {n} 個交易日"
                                     for w, n in missing.items()))
    _update_queue_countdown(n_dates, dates, missing, usable)
    return 0


# PENDING_QUEUE 裡被改寫的區塊標記
_CD_BEGIN = "<!-- FLOW_COUNTDOWN_BEGIN -->"
_CD_END = "<!-- FLOW_COUNTDOWN_END -->"


def _update_queue_countdown(n_dates, dates, missing, usable) -> None:
    """每日改寫 PENDING_QUEUE 的金流一倒數行（2026-09-08 總司令裁示 3）。

    為什麼做成自動的：倒數若靠人記得每天改，第一天就會忘。
    而且**一個過期的倒數比沒有倒數更糟**——會讓人以為快好了。
    這裡直接把當日實際可用天數寫回去，不經人手。
    """
    q = ROOT / "PENDING_QUEUE.md"
    try:
        txt = q.read_text(encoding="utf-8")
        if _CD_BEGIN not in txt or _CD_END not in txt:
            return
        if missing:
            miss_txt = "、".join(
                f"**{w} 日視窗還需 {n} 個交易日**"
                for w, n in sorted(missing.items(), key=lambda kv: int(kv[0])))
            lines = [
                f"- [!] **金流一.4** **阻塞：等資料累積**——目前法人歷史 "
                f"**{n_dates} 個交易日**（{dates[0]}~{dates[-1]}），"
                f"可用視窗 {usable}；{miss_txt}。",
                "  待補：個股頁異常大買（60 日 z）、逆勢買超、法人 20 日均價、"
                "市場頁象限散點圖（需 20 日加速度）。**不得縮短視窗湊數。**",
                "  <sub>此行由 `scripts/build_sector_flow.py` 每日自動改寫。</sub>",
            ]
        else:
            lines = [
                f"- [ ] **金流一.4** **視窗已足夠，可以動工**——法人歷史 "
                f"{n_dates} 個交易日，5／20／60 日視窗全部可用。",
            ]
        head = txt.split(_CD_BEGIN, 1)[0]
        tail = txt.split(_CD_END, 1)[1]
        body = "\n".join(lines)
        q.write_text(head + _CD_BEGIN + "\n" + body + "\n" + _CD_END + tail,
                     encoding="utf-8")
        print("  已更新 PENDING_QUEUE 的金流一倒數行")
    except Exception as e:  # noqa: BLE001
        # 倒數更新失敗不能影響主要產出——這只是文件同步，不是資料
        print(f"  ! 更新 PENDING_QUEUE 倒數失敗（{type(e).__name__}: {e}），"
              f"不影響本次 sector_flow.json 產出")


if __name__ == "__main__":
    raise SystemExit(main())
