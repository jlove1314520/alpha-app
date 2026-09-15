# -*- coding: utf-8 -*-
"""我們（三榜Top20）vs 0050 主圖資料（2026-09-15 總司令三階段裁示【階段三】）。

**只讀`data/picks_ledger.json`的實際回填紀錄，不重新跑回測**（總司令原話：
「重算等於再一次用歷史擬合自己，那就不是前瞻紀錄了」）。三榜（value/
momentum/future）各自分開算一條累積報酬曲線，不合成一條「總分」；0050
用`data/price_history.json`（TWSE STOCK_DAY_ALL全市場端點含括，非新抓
程式，見PENDING_QUEUE.md「我們vs0050」條目階段二記錄）算同一批快照日的
配對報酬。

**持有假設（總司令原話，不藏在程式裡，這裡的常數就是唯一算法依據，
App前端直接讀這份JSON顯示的數字，不得跟這裡的假設不一致）**：
1. 等權重買進當天Top20（picks_ledger每個snapshot本身就是Top20快照）。
2. 持有5個交易日（t5——目前picks_ledger只有t5回填，t20/t60/t120皆為
   null，見PENDING_QUEUE.md階段一記錄，尚不能用）。
3. **成本要扣**：我方（股票）手續費0.1425%×2（買+賣）+證交稅0.3%（賣出）
   =單趟(round-trip)0.585%；0050（ETF）證交稅是0.1%不是股票的0.3%
   （台灣ETF證交稅率較低是公開的稅制事實，不是我方特殊優惠），單趟
   =0.1425%×2+0.1%=0.385%。**這個ETF/股票稅率差異是本腳本主動加的
   誠實區分，不是總司令原文逐字指定，如果總司令認為應該統一用0.3%
   比較，這裡明確可調整，改DEDUCT_COST_PCT即可**。
4. **累積曲線的建構方式（方法論選擇，總司令原文未指定，這裡選最簡單
   可解釋的版本，非唯一可能版本）**：picks_ledger每天都有新snapshot
   （T+5持有期彼此重疊），這裡不建立「每日資金配置」的完整投資組合
   模型（那需要決定重疊部位怎麼分配資金，原始規格未定義），改用
   「依序串接」：把各snapshot（依snapshot_date排序）的（扣成本後）t5
   報酬當作一連串連續的交易依序複利相乘，模擬「賣掉上一批、換入下一批」
   的簡化操作，不是「同時持有多批重疊部位」的完整模型。**這個簡化
   必須寫進圖表旁邊的假設說明，不得默默隱藏**。
5. 0050的配對報酬：對每一個picks_ledger snapshot的日期，查
   `price_history.json`裡0050當天收盤（進場）與5個交易日後收盤（出場），
   算同樣持有5天、同樣扣0050的成本後的報酬，用同一串接方式累積——
   這樣「我們」與「0050」曲線的x軸（交易次數/日期序列）完全對齊，
   才是同基礎比較。

**樣本不足護欄（總司令原話，最重要的一條）**：有效樣本<60個交易日時，
`sample_insufficient=true`，App前端看到這個旗標**不得顯示任何結論性
文字**，結論欄位固定顯示「資料累積中」。這裡只負責算出這個旗標與曲線
本身，不負責畫圖（畫圖在index.html），但誠實地把「有效樣本數」算出來
讓前端判斷。

跑法：`python .github/scripts/build_benchmark_comparison.py`（讀本機
已有的picks_ledger.json/price_history.json，零額外網路請求，可掛進
market.yml的build_picks_ledger.py之後）。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LEDGER_PATH = REPO_ROOT / "data" / "picks_ledger.json"
PRICE_HISTORY_PATH = REPO_ROOT / "data" / "price_history.json"
OUT_PATH = REPO_ROOT / "data" / "benchmark_comparison.json"
TW_TZ = timezone(timedelta(hours=8))

BOARDS = ("value", "momentum", "future")
BENCHMARK_CODE = "0050"
HOLD_WINDOW = "t5"  # 目前唯一已回填的窗口，見模組docstring第2點
STOCK_ROUNDTRIP_COST_PCT = 0.1425 * 2 + 0.3   # 手續費0.1425%×2 + 證交稅0.3%（賣出）
ETF_ROUNDTRIP_COST_PCT = 0.1425 * 2 + 0.1     # 同上，ETF證交稅0.1%（非股票0.3%）
SAMPLE_SUFFICIENT_TRADING_DAYS = 60  # 總司令原話：有效樣本<60個交易日視為不足


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"讀 {path} 失敗：{e}")
        return {}


def _board_series(snapshots: list[dict], board: str) -> list[dict]:
    """依snapshot_date排序，對每個屬於這個board的snapshot，算等權重平均
    t5報酬（扣成本），回傳[{date, raw_return_pct, cost_pct, net_return_pct,
    n_picks}, ...]。缺t5的picks不計入那個snapshot的平均（用當時已回填的
    picks算，不是硬等全部20檔都回填才顯示）。"""
    rows = [s for s in snapshots if s.get("board") == board]
    rows.sort(key=lambda s: s["snapshot_date"])
    out = []
    for snap in rows:
        rets = []
        for p in snap.get("picks", []):
            if p.get("price_stale"):
                continue  # 跟update_picks_ledger_returns.py同一套守門，進場價本身不可靠就不算
            r = (p.get("returns") or {}).get(HOLD_WINDOW)
            if r and r.get("return_pct") is not None:
                rets.append(r["return_pct"])
        if not rets:
            continue  # 這個snapshot的t5還沒到期或全部缺資料，跳過（不是0，是還沒有）
        raw = sum(rets) / len(rets)
        net = raw - STOCK_ROUNDTRIP_COST_PCT
        out.append({
            "date": snap["snapshot_date"],
            "raw_return_pct": round(raw, 4),
            "cost_pct": STOCK_ROUNDTRIP_COST_PCT,
            "net_return_pct": round(net, 4),
            "n_picks": len(rets),
        })
    return out


def _benchmark_series_for_dates(dates: list[str], price_rows: list[dict]) -> dict[str, dict]:
    """對每個日期，找price_history.json裡0050當天收盤與往後第5個「有資料」
    的交易日收盤（用0050自己的序列當日曆，跟update_picks_ledger_returns.py
    的2330代理邏輯同精神，但這裡直接用0050自己的序列，不需要額外代理，
    因為我們只需要0050自己的t5報酬，不需要通用交易日曆）。"""
    by_date = {r["date"]: r["close"] for r in price_rows if r.get("close") is not None}
    all_dates = sorted(by_date.keys())
    idx_of = {d: i for i, d in enumerate(all_dates)}
    out = {}
    for d in dates:
        if d not in idx_of:
            continue
        i = idx_of[d]
        if i + 5 >= len(all_dates):
            continue  # 還沒到5個交易日後，跟picks_ledger的t5未到期是同一種「還沒有」
        entry = by_date[all_dates[i]]
        exit_ = by_date[all_dates[i + 5]]
        raw = (exit_ / entry - 1) * 100
        net = raw - ETF_ROUNDTRIP_COST_PCT
        out[d] = {"date": d, "raw_return_pct": round(raw, 4),
                   "cost_pct": ETF_ROUNDTRIP_COST_PCT, "net_return_pct": round(net, 4)}
    return out


def _compound(rows: list[dict]) -> list[dict]:
    """依序複利串接net_return_pct，回傳附上cum_return_pct與running MDD的序列。"""
    nav = 100.0
    peak = 100.0
    out = []
    for r in rows:
        nav *= (1 + r["net_return_pct"] / 100)
        peak = max(peak, nav)
        dd = (nav / peak - 1) * 100
        out.append({**r, "nav": round(nav, 4), "cum_return_pct": round(nav - 100, 4),
                    "drawdown_pct": round(dd, 4)})
    return out


def _mdd(rows: list[dict]) -> float | None:
    if not rows:
        return None
    return round(min(r["drawdown_pct"] for r in rows), 4)


def _calmar(rows: list[dict], trading_days_per_year: int = 252) -> float | None:
    """年化報酬 ÷ |最大回撤|。年化用「總報酬依實際交易次數換算成年化」的
    簡化法（trade次數×持有天數近似交易日長度）——樣本這麼少時年化本身
    參考價值有限，這也是為什麼<60天要強制標「資料累積中」不給結論。"""
    if not rows:
        return None
    total_days = len(rows) * 5  # 每筆交易對應5個交易日的持有期，這是近似值不是精確交易日計數
    if total_days <= 0:
        return None
    total_return = rows[-1]["nav"] / 100 - 1
    years = total_days / trading_days_per_year
    if years <= 0:
        return None
    annualized = (1 + total_return) ** (1 / years) - 1 if total_return > -1 else None
    mdd = _mdd(rows)
    if annualized is None or mdd is None or mdd == 0:
        return None
    return round(annualized * 100 / abs(mdd), 4)


def main():
    ledger = _load_json(LEDGER_PATH)
    snapshots = ledger.get("snapshots", [])
    price_history = _load_json(PRICE_HISTORY_PATH).get("prices", {})
    benchmark_rows = price_history.get(BENCHMARK_CODE, [])

    boards_out = {}
    for board in BOARDS:
        raw_series = _board_series(snapshots, board)
        dates = [r["date"] for r in raw_series]
        bench_by_date = _benchmark_series_for_dates(dates, benchmark_rows)
        # 只保留「我方跟0050都有資料」的日期，確保兩條線x軸完全對齊（同基礎比較）
        aligned_ours = [r for r in raw_series if r["date"] in bench_by_date]
        aligned_bench = [bench_by_date[r["date"]] for r in aligned_ours]

        ours_curve = _compound(aligned_ours)
        bench_curve = _compound(aligned_bench)
        n = len(aligned_ours)
        gap_pp = None
        if ours_curve and bench_curve:
            gap_pp = round(ours_curve[-1]["cum_return_pct"] - bench_curve[-1]["cum_return_pct"], 4)

        boards_out[board] = {
            "n_comparable_snapshots": n,
            "sample_insufficient": n < SAMPLE_SUFFICIENT_TRADING_DAYS,
            "ours_curve": ours_curve,
            "benchmark_curve": bench_curve,
            "cum_return_pct_ours": ours_curve[-1]["cum_return_pct"] if ours_curve else None,
            "cum_return_pct_benchmark": bench_curve[-1]["cum_return_pct"] if bench_curve else None,
            "gap_pp": gap_pp,
            "mdd_pct_ours": _mdd(ours_curve),
            "calmar_ours": _calmar(ours_curve),
        }

    payload = {
        "meta": {
            "generated_at": datetime.now(TW_TZ).isoformat(),
            "source": "data/picks_ledger.json（實際回填紀錄，非重算回測）+ "
                       "data/price_history.json（0050，TWSE STOCK_DAY_ALL）",
            "hold_window": HOLD_WINDOW,
            "assumption_note": "等權重買進Top20、持有5個交易日、依序串接複利"
                                "（非同時持有多批重疊部位的完整投資組合模型）、"
                                "已扣成本（股票0.1425%×2手續費+0.3%證交稅、"
                                "0050 ETF 0.1425%×2手續費+0.1%證交稅）",
            "sample_sufficient_trading_days": SAMPLE_SUFFICIENT_TRADING_DAYS,
            "benchmark": BENCHMARK_CODE,
        },
        "boards": boards_out,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    for board, b in boards_out.items():
        print(f"{board}: n={b['n_comparable_snapshots']} "
              f"gap={b['gap_pp']} pp  ours={b['cum_return_pct_ours']}%  "
              f"bench={b['cum_return_pct_benchmark']}%  "
              f"insufficient={b['sample_insufficient']}")
    print(f"寫入 {OUT_PATH}")


if __name__ == "__main__":
    main()
