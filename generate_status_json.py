# -*- coding: utf-8 -*-
"""產生/更新 data/STATUS.json——給外部協作者（例如「Cowork」）讀取的單一事實來源。

背景（2026-08-27）：Cowork 只能用完整路徑讀 raw 檔案，沒辦法列目錄、沒辦法讀
commit 紀錄，導致它不知道名字的檔案（例如 market.yml、market_tw.json）就等於
不存在，因而誤判「沒做事」。這支腳本把 `data/` 底下每個檔案、`.github/workflows/`
底下每個 workflow、`index.html` 每個面板實際讀的資料源，都用程式掃出來寫成一份
JSON，不是手寫、不會漏。

**維護規則（使用者裁示）**：每次 commit 有異動到 `data/`、`.github/workflows/`
或 `index.html` 的資料來源時，重跑這支腳本更新 `data/STATUS.json` 再一起 commit。
這支腳本本身不寫死任何面板的資料源清單去「猜」——`APP_DATA_SOURCES` 那份表格是
人工逐行讀過 `index.html` 對照出來的結果（見下方常數），異動到面板資料源時要
連這份表格一起手動更新，不是全自動掃描（那需要真正的 JS 靜態分析，投入產出比
不划算，這裡老實用人工核對＋腳本組裝的方式）。
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
OUT_PATH = DATA_DIR / "STATUS.json"
TW_TZ = timezone(timedelta(hours=8))

GITHUB_REPO = "jlove1314520/alpha-app"
STALE_HOURS = {
    "data/quotes_tw.json": 24,  # 盤中才需要新鮮，這裡用寬鬆門檻，實際過期判斷交給App自己的診斷橫幅
    "data/quotes_us.json": 24,
    "data/market_tw.json": 24,
    "data/market_us.json": 24,
    "data/fundamentals.json": 72,  # 3天，跟App診斷橫幅的門檻一致
    "data/margin_maintenance.json": 72,  # 2026-08-27改排程後：一天一次，3天沒新增才算過期
    "data/fx.json": 48,
    "data/stock_detail.json": 96,  # 財報一季才更新一次，但三大法人/融資融券是每日，用寬鬆門檻涵蓋兩者
    "data/price_history.json": 72,  # 每日累積式更新，跟fundamentals.json同等寬鬆門檻
    "data/quotes_all_tw.json": 72,  # 跟price_history.json同一次排程產生，門檻一致
    "data/earnings_calendar.json": 72,  # 財報日期變動很慢，門檻可以更寬鬆，先跟其他每日檔案一致
    "data/ex_dividend_events.json": 72,  # 跟price_history.json同一次排程產生，門檻一致
    "data/picks_ledger.json": 48,  # 一天一次的前瞻選股快照，跟margin_maintenance.json同等寬鬆門檻
    "data/strategies.json": 168,  # 手動跑generate_strategies_json.py產生，沒有排程，門檻放寬到一週避免誤標stale
    "data/strategy_performance.json": 48,  # 掛market.yml排程更新，跟picks_ledger.json同等寬鬆門檻
    "data/quotes_ibkr.json": 168,  # 只有使用者本機開著IB Gateway+排程在跑才會更新，機器關機/週末沒開很正常，門檻比照strategies.json放寬到一週
}


def _git(*args) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()


def describe_quotes(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    meta = d.get("meta", {})
    # 2026-08-27新增：quotes_us.json才有market_session/extended_hours_matched
    # （P2-新盤前盤後），quotes_tw.json沒有這兩個key，get()回傳None時就不附加。
    ext_bits = ""
    if meta.get("market_session") is not None:
        ext_bits = f" market_session={meta.get('market_session')} extended_hours_matched={meta.get('extended_hours_matched')}"
    return {
        "generated_at": d.get("fetched_at"),
        "records": meta.get("matched"),
        "source": d.get("source"),
        "detail": f"queried={meta.get('queried')} matched={meta.get('matched')} trading_window={meta.get('trading_window')}{ext_bits}",
    }


def describe_market_tw(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    return {
        "generated_at": d.get("fetched_at"),
        "records": len(d.get("sectors", [])),
        "source": "TWSE openapi(MI_INDEX)/TPEx openapi/TAIFEX openapi/TWSE T86",
        "detail": f"sectors={len(d.get('sectors', []))} institutional_history_days={len(d.get('institutional_history', []))} errors={d.get('errors')}",
    }


def describe_market_us(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    return {
        "generated_at": d.get("fetched_at"),
        "records": len(d.get("indices", {})),
        "source": "yfinance",
        "detail": f"indices={list(d.get('indices', {}).keys())}",
    }


def describe_fundamentals(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    meta = d.get("meta", {})
    return {
        "generated_at": meta.get("generated_at"),
        "records": len(d.get("fundamentals", {})),
        "source": "起始種子=research端FinMind快取整理；此後累積更新=TWSE openapi(BWIBBU_ALL/t187ap05_L)",
        "detail": f"ratios_updated={meta.get('ratios_updated_count')} revenue_updated={meta.get('revenue_updated_count')} errors={meta.get('errors')}",
    }


def describe_margin_maintenance(path: Path) -> dict:
    rows = json.loads(path.read_text(encoding="utf-8"))
    last = rows[-1] if rows else {}
    return {
        "generated_at": last.get("date"),
        "records": len(rows),
        "source": "2026-08-27起改排程：TWSE官方MI_MARGN(逐股融資餘額)+STOCK_DAY_ALL(逐股收盤價)算擔保品市值；"
                  "分母(全市場融資金額)仍用FinMind（唯一保留依賴，一天只呼叫一次，風險低）",
        "detail": f"ratio_pct={last.get('ratio_pct')} matched_stocks={last.get('matched_stocks')}（原本是alpha-data獨立目錄手動產生，"
                  "已改掛進market.yml排程，見update_margin_maintenance.py）",
    }


def describe_fx(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    usd = d.get("usd_twd") or {}
    return {
        "generated_at": d.get("fetched_at"),
        "records": 1 if usd else 0,
        "source": "yfinance TWD=X",
        "detail": f"rate={usd.get('rate')} date={usd.get('date')} errors={d.get('errors')}",
    }


def describe_stock_detail(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    stocks = d.get("stocks", {})
    meta = d.get("meta", {})
    with_fin = sum(1 for s in stocks.values() if s.get("financials"))
    with_inst = sum(1 for s in stocks.values() if s.get("institutional"))
    with_margin = sum(1 for s in stocks.values() if s.get("margin"))
    return {
        "generated_at": meta.get("generated_at"),
        "records": len(stocks),
        "source": "TWSE官方t187ap06_L_ci/07_L_ci(財報，僅一般業)+T86(三大法人，跟market_tw.json共用)+MI_MARGN(融資融券，跟大盤維持率共用)",
        "detail": f"財報{with_fin}檔/三大法人{with_inst}檔/融資融券{with_margin}檔（合計{len(stocks)}檔有任一種資料）",
    }


def describe_price_history(path: Path) -> dict:
    """price_history.json（2026-08-27新增，給generate_scores_live.py的technical
    因子用）——TWSE STOCK_DAY_ALL+TPEx tpex_mainboard_quotes累積式OHLCV快照，
    起始種子由research/build_price_history.py讀本機FinMind parquet快取回補。
    2026-08-27新增adj_close（還原權息收盤價，見ex_dividend_events.json）。"""
    d = json.loads(path.read_text(encoding="utf-8"))
    meta = d.get("meta", {})
    prices = d.get("prices", {})
    depths = [len(v) for v in prices.values() if v]
    avg_depth = round(sum(depths) / len(depths), 1) if depths else None
    return {
        "generated_at": meta.get("generated_at"),
        "records": len(prices),
        "source": "TWSE STOCK_DAY_ALL + TPEx tpex_mainboard_quotes（官方開放資料，累積式寫回，免金鑰）",
        "detail": (
            f"平均每檔保留{avg_depth}個交易日（上限90天）。close為原始收盤（未還原權息，"
            "generate_scores_live.py的technical因子仍用這欄）；adj_close為還原權息收盤價"
            f"（2026-08-27新增，題材動能榜relative_strength因子改用這欄）——本輪除權息事件"
            f"新增{meta.get('ex_dividend_events_added')}筆、套用回溯調整{meta.get('ex_dividend_events_applied')}筆，"
            "見ex_dividend_events.json"
        ),
    }


def describe_ex_dividend_events(path: Path) -> dict:
    """ex_dividend_events.json（2026-08-27新增）——每日排程從TWSE官方
    rwd/zh/exRight/TWT48U（除權除息預告表）累積寫入的事件帳本，供
    update_price_history.py回溯調整price_history.json的adj_close用。"""
    d = json.loads(path.read_text(encoding="utf-8"))
    meta = d.get("meta", {})
    events = d.get("events", {})
    total_events = sum(len(v) for v in events.values())
    applied = sum(1 for v in events.values() for ev in v if ev.get("applied") and ev.get("factor_applied"))
    skipped = sum(1 for v in events.values() for ev in v if ev.get("applied") and ev.get("skip_reason"))
    pending = total_events - applied - skipped
    return {
        "generated_at": meta.get("generated_at"),
        "records": total_events,
        "source": "TWSE官方rwd/zh/exRight/TWT48U（除權除息預告表，免金鑰，只回傳未來約5週內事件）",
        "detail": f"{len(events)}檔股票累積共{total_events}筆事件：已套用{applied}筆、"
                   f"因快取資料缺口過大而安全跳過{skipped}筆、尚待處理{pending}筆",
    }


def describe_company_info(path: Path) -> dict:
    """company_info.json（2026-08-27新增，P1抽查發現generate_scores_live.py
    多數股票name/industry是null後補上）——靜態參考資料（公司名稱不常變動），
    不用age-based新鮮度判斷，用INTENTIONALLY_EMPTY同一套機制固定回報ok。"""
    d = json.loads(path.read_text(encoding="utf-8"))
    meta = d.get("meta", {})
    companies = d.get("companies", {})
    return {
        "generated_at": None,
        "records": len(companies),
        "source": meta.get("source"),
        "detail": meta.get("industry_ambiguous_note", ""),
    }


def describe_quotes_all_tw(path: Path) -> dict:
    """quotes_all_tw.json（2026-08-27新增，B4類股成分股清單用）——從
    price_history.json每檔最後兩筆算出的輕量快照（收盤/漲跌%/成交值），
    見update_price_history.py/build_price_history.py的snapshot邏輯。"""
    d = json.loads(path.read_text(encoding="utf-8"))
    meta = d.get("meta", {})
    quotes = d.get("quotes", {})
    return {
        "generated_at": meta.get("generated_at"),
        "records": len(quotes),
        "source": "從data/price_history.json衍生的輕量快照（TWSE STOCK_DAY_ALL+TPEx tpex_mainboard_quotes）",
        "detail": meta.get("note", ""),
    }


def describe_earnings_calendar(path: Path) -> dict:
    """earnings_calendar.json（2026-08-27新增，P2財報行事曆）——見
    fetch_earnings_calendar.py：yfinance get_calendar()抓下一次財報日
    （穩定），get_earnings_dates()推估盤前/盤後時段目前在這台機器持續遇到
    curl_cffi對guce.yahoo.com的DNS解析問題（socket.gethostbyname()正常，
    curl_cffi內部解析失敗，環境特定問題非程式bug），estimated_session誠實
    降級為'unknown'，不影響next_earnings_date本身的可靠性。"""
    d = json.loads(path.read_text(encoding="utf-8"))
    meta = d.get("meta", {})
    earnings = d.get("earnings", {})
    known_session = sum(1 for e in earnings.values() if e.get("estimated_session") != "unknown")
    return {
        "generated_at": meta.get("generated_at"),
        "records": len(earnings),
        "source": meta.get("source"),
        "detail": f"coverage={meta.get('coverage')} session已知={known_session}/{len(earnings)} errors={meta.get('errors')}",
    }


def describe_paper_trades(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    return {
        "generated_at": d.get("generated_at"),
        "records": len(d.get("strategies", [])),
        "source": "無（尚未串接任何真實券商API，App誠實顯示空狀態，不是資料源故障）",
        "detail": "schema_version=%s，strategies為空陣列是刻意設計，不是bug" % d.get("schema_version"),
    }


def describe_strategies(path: Path) -> dict:
    """data/strategies.json（2026-08-29新增，策略監控台）——
    `research/generate_strategies_json.py`從真實檔案（scores*.json/
    picks_ledger.json/TRIALS_LEDGER.md/B24_RESULTS.md）推導產生，
    App「交易→策略監控台」分頁讀這個檔案渲染卡片。"""
    d = json.loads(path.read_text(encoding="utf-8"))
    strategies = d.get("strategies", [])
    status_counts: dict[str, int] = {}
    for s in strategies:
        st = s.get("status", "unknown")
        status_counts[st] = status_counts.get(st, 0) + 1
    return {
        "generated_at": d.get("generated_at"),
        "records": len(strategies),
        "source": "research/generate_strategies_json.py（從scores*.json/picks_ledger.json/TRIALS_LEDGER.md/B24_RESULTS.md推導，非手寫）",
        "detail": f"status分布={status_counts}",
    }


def describe_strategy_performance(path: Path) -> dict:
    """data/strategy_performance.json（2026-08-29新增，策略監控台升級）——
    `research/update_strategy_performance.py`每個台股開盤日排程更新，
    逐日mark-to-market累積前向紙上模擬（forward paper），嚴禁事後補建。
    這是`data/strategies.json`的`forward_paper`欄位的真正資料來源。"""
    d = json.loads(path.read_text(encoding="utf-8"))
    strategies = d.get("strategies", {})
    summary = {
        sid: f"{s.get('trading_days_count')}天/{s.get('forward_return_todate_pct')}%"
        for sid, s in strategies.items()
    }
    return {
        "generated_at": d.get("generated_at"),
        "records": len(strategies),
        "source": "research/update_strategy_performance.py（每日mark-to-market，逐日累積不可回填）",
        "detail": f"as_of_trading_date={d.get('as_of_trading_date')} 各策略(交易日數/累積報酬)={summary}",
    }


def describe_quotes_ibkr(path: Path) -> dict:
    """data/quotes_ibkr.json（2026-09-01新增）——IBKR本機IB Gateway paper帳戶
    即時/延遲報價，由本機`research/ibkr_quotes.py`排程觸發（不經GitHub
    Actions，那邊連不到使用者本機的Gateway），只有這台機器有在跑排程時才會
    持續更新，其他機器/裝置看到的是最後一次push的快照，不代表當下就是壞的。
    `connected:false`是誠實的失敗狀態（IB Gateway沒開/連線失敗），不當作
    status_from_age()意義上的錯誤，只在detail裡註明原因。"""
    d = json.loads(path.read_text(encoding="utf-8"))
    quotes = d.get("quotes", {})
    n_with_data = sum(1 for q in quotes.values() if q.get("last") is not None)
    return {
        "generated_at": d.get("fetched_at"),
        "records": len(quotes),
        "source": "research/ibkr_quotes.py（本機IB Gateway paper帳戶，非GitHub Actions排程）",
        "detail": f"connected={d.get('connected')} account_type={d.get('account_type')} "
                  f"error={d.get('error')} 有報價數={n_with_data}/{len(quotes)}",
    }


def describe_picks_ledger(path: Path) -> dict:
    """data/picks_ledger.json（2026-08-28新增追蹤，資料源禮儀補洞item 3）——
    三榜（價值成長/題材動能/未來性）Top20前瞻選股快照，`build_picks_ledger.py`
    每次market.yml排程跑完寫入，鐵律是只能事前快照、不能事後補建（見BACKLOG
    B24）。這裡沒有頂層generated_at欄位，用meta.last_snapshot_at當新鮮度
    依據；之前沒有專屬解析器，會落到generic fallback（generated_at=None）
    被status_from_age()誤判成"error"，其實資料一直是好的，只是沒人幫它寫
    解析器。"""
    d = json.loads(path.read_text(encoding="utf-8"))
    meta = d.get("meta", {})
    snapshots = d.get("snapshots", [])
    boards = sorted({s.get("board") for s in snapshots if s.get("board")})
    latest_dates = {}
    for s in snapshots:
        b = s.get("board")
        sd = s.get("snapshot_date")
        if b and sd and (b not in latest_dates or sd > latest_dates[b]):
            latest_dates[b] = sd
    return {
        "generated_at": meta.get("last_snapshot_at"),
        "records": len(snapshots),
        "source": ".github/scripts/build_picks_ledger.py（market.yml排程，三榜產生後、commit前快照，非回測）",
        "detail": f"total_snapshots={meta.get('total_snapshots')} boards={boards} "
                  f"latest_snapshot_date_by_board={latest_dates}",
    }


DESCRIBERS = {
    "quotes_tw.json": describe_quotes,
    "quotes_us.json": describe_quotes,
    "market_tw.json": describe_market_tw,
    "market_us.json": describe_market_us,
    "fundamentals.json": describe_fundamentals,
    "margin_maintenance.json": describe_margin_maintenance,
    "paper_trades.json": describe_paper_trades,
    "fx.json": describe_fx,
    "stock_detail.json": describe_stock_detail,
    "price_history.json": describe_price_history,
    "company_info.json": describe_company_info,
    "quotes_all_tw.json": describe_quotes_all_tw,
    "earnings_calendar.json": describe_earnings_calendar,
    "ex_dividend_events.json": describe_ex_dividend_events,
    "picks_ledger.json": describe_picks_ledger,
    "quotes_ibkr.json": describe_quotes_ibkr,
    "strategies.json": describe_strategies,
    "strategy_performance.json": describe_strategy_performance,
}


def status_from_age(generated_at: str | None, stale_hours: float) -> str:
    if not generated_at:
        return "error"
    try:
        ts = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except ValueError:
        return "error"
    age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    return "ok" if age_h <= stale_hours else "stale"


# 這些檔案的「無資料/generated_at為null」是刻意設計（尚未串接真實資料源），不是
# 排程失敗，用age-based判斷會誤標成error，這裡明確排除、固定回報"ok"。
INTENTIONALLY_EMPTY = {"paper_trades.json", "company_info.json"}


def describe_scores(path: Path) -> dict:
    """scores.json（2026-08-27新增追蹤，使用者要求）——注意這個檔案在repo根目錄，
    不在data/底下。**2026-08-27（晚）新增雙管線**：`research/generate_scores_v2.py`
    （本機/互動session手動執行，讀research端FinMind parquet快取，因子覆蓋較完整）
    跟 `research/generate_scores_live.py`（GitHub Actions每日排程執行，只讀repo內
    fundamentals.json/stock_detail.json，不依賴parquet/FinMind，但technical/analyst/
    catalyst三項恆缺）都會寫這同一份scores.json——用meta.engine_version區分
    這次是哪條管線產生的（"scoring-v2" vs "scoring-live-json"）。"""
    d = json.loads(path.read_text(encoding="utf-8"))
    meta = d.get("meta", {})
    stocks = d.get("stocks", [])
    coverages = [s.get("coverage") for s in stocks if s.get("coverage") is not None]
    avg_coverage = round(sum(coverages) / len(coverages), 3) if coverages else None
    engine = meta.get("engine_version", "unknown")
    source = ("research/generate_scores_v2.py（本機/互動session手動執行，非GitHub Actions）"
              if engine == "scoring-v2" else
              "research/generate_scores_live.py（GitHub Actions market.yml每日排程自動執行，"
              "JSON-only，不依賴parquet/FinMind）"
              if engine == "scoring-live-json" else
              "research/generate_scores_momentum.py（GitHub Actions market.yml每日排程自動執行，"
              "題材動能榜，跟價值成長榜物理分離的獨立引擎，見weights_frozen_momentum.json）"
              if engine == "scoring-momentum-v1" else
              "research/generate_scores_future.py（GitHub Actions market.yml每日排程自動執行，"
              "未來性濾網(a)類因子，跟另外兩榜物理分離的獨立引擎，見weights_frozen_future.json）"
              if engine == "scoring-future-v1" else f"未知engine_version={engine}")
    return {
        "generated_at": meta.get("generated_at"),
        "records": len(stocks),
        "source": source,
        "detail": f"engine_version={engine} universe_size={meta.get('universe_size')} avg_coverage={avg_coverage} "
                  f"weights_hash={(meta.get('weights_hash') or '')[:12]} "
                  f"coverage_collapse_warning={meta.get('coverage_collapse_warning')} "
                  f"backtest_status={meta.get('backtest_status')}",
    }


def build_data_files() -> list[dict]:
    out = []
    for path in sorted(DATA_DIR.glob("*.json")):
        if path.name == "STATUS.json":
            continue
        if path.name == "rate_limit_state.json":
            # 2026-08-28新增：這個檔案不是「App資料」，是跨process共用的節流/
            # 斷路狀態，已經有專屬的build_rate_limit_status()整理成人類看得懂
            # 的格式放進STATUS.json的rate_limit_status欄位——這裡跳過，不要
            # 讓它又混進data_files清單、被通用解析器誤標成「未知/error」。
            continue
        rel = f"data/{path.name}"
        describer = DESCRIBERS.get(path.name)
        if describer:
            info = describer(path)
        else:
            info = {"generated_at": None, "records": None, "source": "未知（generate_status_json.py 沒有對應的解析器，需要補上）", "detail": ""}
        entry = {"path": rel, **info}
        if path.name in INTENTIONALLY_EMPTY:
            entry["status"] = "ok"
        else:
            entry["status"] = status_from_age(info.get("generated_at"), STALE_HOURS.get(rel, 24))
        out.append(entry)

    scores_path = REPO_ROOT / "scores.json"
    if scores_path.exists():
        info = describe_scores(scores_path)
        entry = {"path": "scores.json", **info}
        # 2026-08-27：現在有GitHub Actions每日排程（generate_scores_live.py）維持新鮮度，
        # 門檻收回跟其他每日檔案一致（24小時起，稍微放寬給收盤後排程時間差）。
        entry["status"] = status_from_age(info.get("generated_at"), 30)
        out.append(entry)

    scores_momentum_path = REPO_ROOT / "scores_momentum.json"
    if scores_momentum_path.exists():
        info = describe_scores(scores_momentum_path)
        entry = {"path": "scores_momentum.json", **info}
        entry["status"] = status_from_age(info.get("generated_at"), 30)
        out.append(entry)

    scores_future_path = REPO_ROOT / "scores_future.json"
    if scores_future_path.exists():
        info = describe_scores(scores_future_path)
        entry = {"path": "scores_future.json", **info}
        entry["status"] = status_from_age(info.get("generated_at"), 30)
        out.append(entry)
    return out


def fetch_workflow_runs() -> dict[str, dict]:
    """回傳 {workflow檔名: {name, last_run(ISO), last_status}}。網路失敗就回傳空dict，
    對應欄位在輸出裡會是 null，不是拿假資料頂替。"""
    if requests is None:
        return {}
    try:
        r = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows", timeout=15)
        r.raise_for_status()
        workflows = r.json().get("workflows", [])
    except Exception:
        return {}
    out = {}
    for w in workflows:
        path = w.get("path", "")
        if not path.startswith(".github/workflows/"):
            continue
        fname = path.split("/")[-1]
        entry = {"name": w.get("name"), "last_run": None, "last_status": None}
        try:
            rr = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{w['id']}/runs?per_page=1", timeout=15)
            rr.raise_for_status()
            runs = rr.json().get("workflow_runs", [])
            if runs:
                entry["last_run"] = runs[0].get("created_at")
                entry["last_status"] = runs[0].get("conclusion") or runs[0].get("status")
        except Exception:
            pass
        out[fname] = entry
    return out


def build_workflows() -> list[dict]:
    live = fetch_workflow_runs()
    known = {
        "market.yml": "台股收盤後(06:10 UTC)/美股收盤後(21:30 UTC)，週一至週五",
        "quotes.yml": "盤中每10分鐘：台股09:00-13:30、美股13:30-21:00(左右)，週一至週五",
    }
    out = []
    for fname, schedule in known.items():
        path = REPO_ROOT / ".github" / "workflows" / fname
        if not path.exists():
            continue
        info = live.get(fname, {})
        out.append({
            "file": f".github/workflows/{fname}",
            "name": info.get("name"),
            "schedule": schedule,
            "last_run": info.get("last_run"),
            "last_status": info.get("last_status"),
        })
    return out


# 人工逐行核對 index.html 對照出來的結果（見本檔案docstring說明，不是自動掃描）。
APP_DATA_SOURCES = [
    {"panel": "今日頁·大盤速覽（含sparkline）", "source": "data/market_tw.json + data/market_us.json（2026-08-27新增近20日收盤sparkline）"},
    {"panel": "今日頁·自選股報價（主價格）", "source": "data/quotes_tw.json + data/quotes_us.json（美股2026-08-27新增extended_hours：yfinance盤前/盤後價，跟Finnhub regular quote分開顯示，見panel下方風險揭露）"},
    {"panel": "今日頁·自選股財報行事曆徽章（僅美股，21天內才顯示）", "source": "data/earnings_calendar.json（yfinance get_calendar()，2026-08-27新增）"},
    {"panel": "今日頁·自選股sparkline走勢", "source": "data/quotes_tw.json（TWSE STOCK_DAY，僅上市股票；上櫃約24檔查不到，見known_limitations）+ data/quotes_us.json（yfinance），2026-08-27起不再打FinMind"},
    {"panel": "選股頁·價值成長榜/題材動能榜/未來性濾網（2026-08-27新增三榜切換）", "source": "scores.json（generate_scores_live.py，財報導向）+ scores_momentum.json（generate_scores_momentum.py，題材動能導向）+ scores_future.json（generate_scores_future.py，未來性(a)類因子：法人籌碼行為+毛利率品質+產能利用率代理）——三榜物理分離、因子/權重各自版本控管，回測前都固定顯示「本榜為資料排序，尚未經過組合策略回測驗證」"},
    {"panel": "今日頁·匯率", "source": "data/fx.json（yfinance TWD=X，2026-08-27起不再打FinMind）"},
    {"panel": "今日頁·AI盤前日報", "source": "無（誠實佔位「功能建置中」，非資料源故障）"},
    {"panel": "今日頁·總資產/已實現損益", "source": "無（尚未串接券商，誠實佔位）"},
    {"panel": "市場頁·大盤指數（含sparkline）", "source": "data/market_tw.json + data/market_us.json"},
    {"panel": "市場頁·類股表現(熱力圖)", "source": "data/market_tw.json（sectors，TWSE MI_INDEX 27類）"},
    {"panel": "市場頁·三大法人買賣超(全市場)", "source": "data/market_tw.json（institutional_history，TWSE T86加總）"},
    {"panel": "市場頁·主流題材chips", "source": "FinMind TaiwanStockPrice（8大產業指數Trading_money，仍為舊版本邏輯，未遷移）"},
    {"panel": "市場頁·期貨籌碼", "source": "FinMind TaiwanFuturesInstitutionalInvestors（TX，未遷移；大盤期貨價格本身已在market_tw.json）"},
    {"panel": "個股頁·總覽·走勢圖", "source": "FinMind TaiwanStockPrice / USStockPrice（未遷移）"},
    {"panel": "個股頁·總覽·PER/PBR/殖利率/月營收YoY", "source": "data/fundamentals.json"},
    {"panel": "個股頁·營收·月營收圖", "source": "data/fundamentals.json"},
    {"panel": "個股頁·營收·AI營收解讀", "source": "無（誠實佔位「功能建置中」）"},
    {"panel": "個股頁·財報·EPS/毛利率/營益率/ROE", "source": "data/stock_detail.json（TWSE官方t187ap06_L_ci/07_L_ci，2026-08-27起不再打FinMind；僅涵蓋「上市一般業」，上櫃/金融控股/證券/保險等特殊分類查不到，App會顯示原因）"},
    {"panel": "個股頁·財報·自由現金流(FCF)", "source": "無（尚未接線，非無來源——2026-08-28查證更正：TWSE/TPEx官方openapi確實無現金流量表端點，但FinMind有TaiwanStockCashFlowsStatement(2008年起，涵蓋上市/上櫃/興櫃)，已排入BACKLOG B27：季資料、一季抓一次、硬快取、走排程Actions→JSON，不client-side直抓）"},
    {"panel": "個股頁·籌碼·三大法人買賣超", "source": "data/stock_detail.json（TWSE T86，跟market_tw.json共用同一次呼叫，2026-08-27起不再打FinMind；涵蓋全部上市公司含金融股，2026-08-27修正過度篩選的bug）"},
    {"panel": "個股頁·籌碼·融資融券", "source": "data/stock_detail.json（TWSE MI_MARGN，跟大盤融資維持率共用同一次呼叫，2026-08-27起不再打FinMind；涵蓋全部上市公司含金融股；估算融資維持率為App自算，非官方資料）"},
    {"panel": "個股頁·AI·個股簡報/券商報告雷達", "source": "無（誠實佔位「功能建置中」）"},
    {"panel": "交易頁·策略/機器人列表", "source": "data/paper_trades.json（空陣列，誠實佔位，未串接任何真實券商API）"},
    {"panel": "交易頁·策略監控台（2026-08-29升級：前向績效曲線+排行+明細）", "source": "data/strategies.json（research/generate_strategies_json.py從scores*.json/picks_ledger.json/TRIALS_LEDGER.md/B24_RESULTS.md/data/strategy_performance.json推導）；forward_paper欄位來自data/strategy_performance.json（research/update_strategy_performance.py每個台股開盤日排程，逐日mark-to-market，掛market.yml）"},
    {"panel": "交易頁·大盤融資維持率", "source": "data/margin_maintenance.json（2026-08-27起改排程：分子TWSE官方MI_MARGN/STOCK_DAY_ALL，分母仍FinMind，見known_limitations）"},
    {"panel": "日誌頁·本週損益/AI週覆盤/交易紀錄", "source": "無（尚無交易紀錄，誠實佔位）"},
]

# 2026-08-27新增（使用者要求）：每個關鍵欄位的「主來源→備援→推導→標示不可得」
# 回退鏈，架構層文件——單點依賴視為架構缺陷，不是外部限制（使用者原話）。
FIELD_FALLBACK_CHAINS = [
    {
        "field": "EPS（每股盈餘）／earnings_growth因子",
        "chain": [
            "1. FinMind TaiwanStockFinancialStatements（季度財報EPS年增率，research pipeline既有）",
            "2. 用PER反推TTM EPS（source=\"derived_from_per_ttm\"）：收盤價÷本益比，"
            "在as_of跟約252個交易日前各反推一次算年增率——完全用已快取的PER+價格"
            "時間序列，不需要新的網路請求（2026-08-27新增，score_v2.py::_eps_yoy_derived_from_per()）",
            "3. yfinance trailingEps（尚未實作，列為後續項目）",
            "4. 標示不可得（factors欄位不出現在該檔的factors物件裡）",
        ],
        "source_marking": "scores.json每檔的factors.earnings_growth.raw.eps_yoy_source標記實際用哪一層",
    },
    {
        "field": "月營收",
        "chain": [
            "1. TWSE openapi t187ap05_L（上市）/ TPEx openapi mopsfin_t187ap05_OB（上櫃，"
            "2026-08-27新增）——每日排程累積式更新，見update_fundamentals_daily.py",
            "2. 研究端FinMind TaiwanStockMonthRevenue快取（2026-08-27手動快照的種子資料，"
            "上述官方端點更新不到的舊值）",
            "3. 標示不可得",
        ],
        "source_marking": "fundamentals.json目前未逐筆標記來源是TWSE或TPEx（兩者都寫進同一個month_revenue結構），"
                          "之後如需精確稽核要另外補上per-entry的source欄位",
    },
    {
        "field": "價量（股價/成交量）",
        "chain": [
            "1. TWSE MIS即時行情（quotes_tw.json，盤中）/ yfinance TWD=X等（quotes_us.json）",
            "2. TWSE STOCK_DAY單股歷史日線（sparkline用，僅TWSE上市，2026-08-27新增，"
            "需要瀏覽器風格Referer/User-Agent才不會間歇性429，見fetch_quotes_tw.py）",
            "3. FinMind TaiwanStockPrice/USStockPrice（個股頁走勢圖，尚未遷移，仍在用）",
            "4. 標示不可得",
        ],
        "source_marking": "quotes_tw.json每檔的sparkline_date欄位記錄該筆sparkline實際抓取日期",
    },
    {
        "field": "本益比/淨值比（PER/PBR）",
        "chain": [
            "1. TWSE openapi BWIBBU_ALL（上市）/ TPEx openapi tpex_mainboard_peratio_analysis"
            "（上櫃，2026-08-27新增）——每日排程累積式更新",
            "2. 自行由EPS/BPS計算（尚未實作——目前若BWIBBU/TPEx兩者都失敗就直接標不可得，"
            "沒有再用stock_detail.json的EPS+t187ap07的淨值反推PER/PBR這一層，是可以再補的一層）",
            "3. 標示不可得",
        ],
        "source_marking": "fundamentals.json每檔的ratios.date記錄實際取得日期",
    },
    {
        "field": "上櫃(TPEx)股票總則",
        "chain": [
            "2026-08-27修正：fundamentals.json（PER/PBR/月營收）已補上TPEx對應端點，不再"
            "只靠TWSE。stock_detail.json（財報EPS/毛利率/ROE、三大法人、融資融券）跟"
            "quotes_tw.json的sparkline目前仍只有TWSE版本，上櫃股票這幾項還是空缺"
            "——不是「TPEx沒有對應資料」（TPEx其實有t187ap06_O系列財報端點），"
            "是還沒接，見todo。",
        ],
        "source_marking": None,
    },
]

TODO = [
    {"item": "B16：價值成長榜+題材動能榜都必須各自回測驗證", "priority": "P0", "blocker": "使用者2026-08-27策略層面裁示：兩榜都是「資料排序」，不是驗證過的策略，回測完成/使用者同意前App已固定顯示「本榜為資料排序，尚未經過組合策略回測驗證，不代表能贏大盤」。回測規格：明確交易規則(換股頻率/持股檔數/進出場/停損/單檔上限/全成本)+三個必要對照(動態隨機對照組1000次/買進持有加權指數/對大盤回歸的alpha+beta+顯著性)+評判順序(淨利與MDD達標→Sortino→alpha顯著→夏普最後→勝率不看)。未經使用者同意不得解鎖holdout。尚未開始。"},
    {"item": "題材動能榜的chip_concentration因子用「買超張數」而非「買超佔股本比」", "priority": "P2", "blocker": "沒有現成的已發行股數資料源，是刻意的範圍縮減（跟generate_scores_live.py的chips因子同一個既有簡化）"},
    {"item": "題材動能榜的sector_capital_flow/relative_strength依賴的歷史資料才剛開始累積", "priority": "P2", "blocker": "institutional.history目前只有1-5天（daily排程剛開始跑），price_history.json的turnover欄位也才剛新增，覆蓋率會隨時間自然加深，不是bug"},
    {"item": "未來性濾網的customer_concentration（營收客戶集中度）因子未實作", "priority": "P2", "blocker": "沒有現成的免費資料源（需要財報附註揭露的前五大客戶占比，公開資料無結構化格式可抓）"},
    {"item": "未來性濾網的capacity_utilization_proxy只算目前水準、不是使用者原本要的「趨勢」", "priority": "P2", "blocker": "update_stock_financials.py目前只保留最新一筆non_current_assets_latest，沒有retained歷史序列，需要額外累積才能算趨勢；且「非流動資產」不是精確的「固定資產」，是t187ap07_L_ci沒有單獨固定資產欄位下的近似代理"},
    {"item": "未來性濾網(b)類（事件資料）/(c)類（AI質性研判）因子未實作", "priority": "P2", "blocker": "(b)類依賴訊號管線骨架(BACKLOG.md B19)+docs/Alpha_新聞與供應鏈連動_設計小抄.md既定規格(news_fetch.py/supply_chain.json)先完成；(c)類依賴(b)類的事件資料/供應鏈圖作為AI研判輸入素材，且依使用者規則不計入量化總分、須另闢區塊呈現"},
    {"item": "個股頁美股分頁完全不支援財報/FCF（BACKLOG B29）", "priority": "P2", "blocker": "2026-08-28查證更正：yfinance提供.financials/.balance_sheet/.cashflow（損益表/資產負債表/現金流量表），可做、排隊中——接線前先實測確認欄位確實存在再接，不要假設。已排入BACKLOG B29，尚未開始"},
    {"item": "個股頁美股分頁完全不支援月營收/三大法人/融資融券", "priority": "P2", "blocker": "月營收：美股公司無此揭露義務，結構性不存在，非資料源缺漏。三大法人/融資融券：無「每日」免費對應資料——替代方案=SEC 13F(季度機構持股)+FINRA放空餘額(週)，但顆粒度跟台股「每日」不同，若要做需在App明確標「季/週資料非每日」，2026-08-28使用者裁示先如實揭露，暫不列入排隊"},
    {"item": "個股頁財報FCF（BACKLOG B27）", "priority": "P2", "blocker": "2026-08-27查證：TWSE/TPEx openapi都無現金流量表端點，MOPS網頁查詢端點又被反爬蟲擋——但2026-08-28更正：FinMind有TaiwanStockCashFlowsStatement(2008+，上市櫃興櫃)，可做、排隊中，非無來源。規劃：季資料一季抓一次、硬快取、走排程Actions→JSON，不client-side直抓，納入節流/斷路器登記，尚未開始接線"},
    {"item": "stock_detail.json財報(EPS/毛利率/ROE)僅涵蓋TWSE上市「一般業」，上櫃/金融控股/證券/保險未涵蓋", "priority": "P2", "blocker": "TPEx其實有對應端點(mopsfin_t187ap06_O_ci等)，TWSE金融股也有(t187ap06_L_bd/fh/ins/mim等)，只是還沒接——已知可行，非無來源"},
    {"item": "個股頁自選股sparkline約24檔上櫃股票查不到（quotes_tw.json）", "priority": "P2", "blocker": "TWSE STOCK_DAY端點是TWSE專屬，尚未找到TPEx對應的逐股歷史日線端點（注意：這跟fundamentals.json的TPEx PER/月營收已修正是不同的資料/不同端點）"},
    {"item": "個股走勢圖(價格歷史)脫離FinMind", "priority": "P2", "blocker": "可行，跟sparkline同一個TWSE STOCK_DAY端點（TW）/yfinance（US），只是要決定涵蓋範圍跟歷史長度，尚未實作"},
    {"item": "主流題材chips 脫離FinMind", "priority": "P2", "blocker": "MI_INDEX有類股價格/漲跌%但無成交值，尚未找到TWSE官方逐類股成交值端點；跟使用者要求的「題材生命週期」功能設計高度相關，建議合併處理"},
    {"item": "期貨籌碼(三大法人期貨部位) 脫離FinMind", "priority": "P2", "blocker": "探測過TAIFEX openapi常見端點命名，只找到「大額交易人」資料(跟三大法人分類不同)，需人工查閱TAIFEX網站確認"},
    {"item": "大盤融資維持率的分母(全市場融資金額)仍依賴FinMind", "priority": "P1", "blocker": "TWSE/TPEx官方均無對應端點，只有逐股融資餘額(張)；已完成：該次呼叫失敗時明確寫入data_incomplete=true，App顯示「資料不完整」而非沿用舊值"},
    {"item": "score_live.py的earnings_growth因子沒有PER反推EPS的備援", "priority": "P2", "blocker": "研究端的_eps_yoy_derived_from_per()備援需要「約一年前的PER快照」，但fundamentals.json的ratios只存最新一筆、沒有retained歷史序列，需要另開一份PER歷史累積檔才能補上這條備援"},
    {"item": "generate_scores_live.py沒有規模分層排名", "priority": "P2", "blocker": "revenue_momentum沒有per股票的每日成交量/市值資料可以分層，是刻意的範圍縮減；technical因子已於2026-08-27接上data/price_history.json解決"},
    {"item": "generate_scores_live.py的technical因子(MA60)仍用未還原權息的close", "priority": "P2", "blocker": "2026-08-27已為題材動能榜的relative_strength因子修好還原權息(price_history.json新增adj_close欄位，見known_limitations)，但generate_scores_live.py的technical因子還沒改用adj_close，MA60在除權息當天前後仍會有跳空失真——欄位已存在，只是還沒切過去，是可以直接補的一層"},
    {"item": "月營收/PER來源沒有逐筆標記是TWSE或TPEx", "priority": "P2", "blocker": "fundamentals.json目前TWSE跟TPEx資料寫進同一個結構，沒有per-entry的來源標記，之後要精確稽核需要補上"},
    {"item": "PER/PBR缺乏「自行由EPS/BPS計算」這一層備援", "priority": "P2", "blocker": "目前fundamentals.json的PER/PBR只有BWIBBU_ALL/TPEx兩層，沒有再用stock_detail.json的EPS+資產負債表淨值反推這一層備援"},
    {"item": "CLAUDE.md候選：美股報價/AI盤前日報真新聞/Phase2券商下單研究", "priority": "P2", "blocker": "尚未排序，等使用者指示"},
]

KNOWN_LIMITATIONS = [
    "【策略層面，最重要】2026-08-27新增題材動能榜（scores_momentum.json）+未來性濾網（scores_future.json），跟價值成長榜（scores.json）三榜並列——三榜都尚未經過組合策略回測驗證，App固定顯示「本榜為資料排序，尚未經過組合策略回測驗證，不代表能贏大盤」，見TODO的B16項目。權重是專家判斷的初始設計值（weights_frozen_momentum.json/weights_frozen_future.json），不是回測最佳化結果。",
    "2026-08-27修正P0 bug（使用者回報）：題材動能榜relative_strength因子改用還原權息收盤價（price_history.json新增adj_close欄位）——來源雙軌：一次性回補讀research端FinMind TaiwanStockDividend本機快取（research/build_price_history.py），之後每日排程改讀TWSE官方rwd/zh/exRight/TWT48U除權息預告表累積事件、回溯調整（.github/scripts/update_price_history.py，見data/ex_dividend_events.json）——刻意不在每日排程呼叫FinMind，維持JSON-only架構原則。已知殘留限制：(1)TWT48U只回傳未來約5週的事件預告，不支援歷史查詢，故涵蓋率隨每天累積逐步提高，剛上線這幾週少數個股可能還沒回溯到；(2)實測發現少數股票(如2420/2227/6216/8442等8檔)的research端FinMind快取已經停在很久以前(2024-12-31)，導致「除權息日前一筆可用資料」距離超過10天，判定無法安全定錨調整係數，這類事件會被跳過(adj_close退回等於close，不會比修正前更差)並記錄skip_reason，不會靜默套用錯誤係數。",
    "margin_maintenance.json：分母（全市場融資金額）仍用FinMind單一輕量呼叫（一天一次、抓全市場加總非逐股歷史），若失敗當天會明確寫入data_incomplete=true，App顯示「資料不完整」，不會沿用舊值假裝正常。",
    "stock_detail.json：財報(EPS/毛利率/ROE)只涵蓋TWSE上市「一般業」，金融控股/證券/保險等特殊產業分類、以及全部上櫃(TPEx)股票查不到（TPEx其實有對應端點，只是還沒接，見todo）。"
    "三大法人/融資融券2026-08-27（P1-新）已補上TPEx上櫃股票（tpex_3insti_daily_trading/tpex_mainboard_margin_balance）："
    "三大法人涵蓋檔數1,083→1,990檔、融資融券1,063→1,983檔，scores.json全市場平均coverage 0.341→0.376（chips因子權重14%受益最多）。"
    "FCF：TWSE/TPEx官方均無現金流量表端點，MOPS網頁查詢被反爬蟲擋（已重新驗證，非未查證的臆測）——但2026-08-28更正：這只是「TWSE/TPEx官方路徑」走不通，FinMind TaiwanStockCashFlowsStatement(2008+)可行，已排入BACKLOG B27排隊中，不是永久性缺口。",
    "quotes_tw.json：自選股sparkline約24檔上櫃(TPEx)股票查不到（TWSE STOCK_DAY端點是TWSE專屬）。",
    "個股頁美股分頁：月營收結構性不存在（美股公司無揭露義務）；三大法人/融資融券無「每日」免費對應（替代=SEC 13F季度+FINRA放空週資料，顆粒度不同，暫不列入排隊）；財報/FCF已查證yfinance可行，排入BACKLOG B29。",
    "個股走勢圖、主流題材chips、期貨籌碼，仍100%依賴FinMind免費額度，額度用盡時會誠實顯示連線失敗（不是假資料）。",
    "2026-08-27發現：這台機器目前曾被FinMind IP封鎖過（非單純額度用盡），research/finmind_client.py原本完全沒有請求節流——已加上每次真正網路請求間至少0.35秒的節流，但這只能降低未來再次觸發封鎖的機率，無法解除已經發生的封鎖，也不是精確調校過的數字。",
    "scores.json（選股頁分數）2026-08-27新增GitHub Actions每日排程（research/generate_scores_live.py，market.yml），只讀repo內JSON、不依賴parquet/FinMind，不會再因為研究者本機沒開機而停擺——但這條JSON-only路徑覆蓋率上限約0.74（technical/analyst/catalyst三項恆缺），跟研究端手動執行（research/generate_scores_v2.py，因子較完整）互不覆蓋衝突，用meta.engine_version分辨這次是哪條管線產生的。",
    "本檔案（STATUS.json）由generate_status_json.py產生，APP_DATA_SOURCES那份面板對照表是人工核對、不是自動掃描——異動面板資料源時要記得同步更新腳本裡的常數，否則這份清單會跟實際程式碼不同步。",
    "earnings_calendar.json：yfinance get_calendar()（下一次財報日期）穩定可用，但get_earnings_dates()（用來推估盤前/盤後公布時段）在這台機器持續遇到curl_cffi對guce.yahoo.com的DNS解析失敗（socket.gethostbyname()本身正常，是curl_cffi內部的環境特定問題，不是程式bug）——estimated_session因此誠實降級為'unknown'，不影響next_earnings_date本身的可靠性；GitHub Actions runner環境不一定有同樣的DNS問題，之後排程實跑可能就會恢復正常。",
]


def build_rate_limit_status() -> dict:
    """2026-08-28新增（使用者裁示「428是我們自己打出來的」，「資料源禮儀」
    規則b：收到428/403就停打該來源至少2小時，寫入STATUS）——讀
    `data/rate_limit_state.json`（各.github/scripts與research腳本共用的
    跨process節流/斷路狀態檔），整理成人類看得懂的摘要，讓使用者/協作者
    一眼看到目前哪些來源在封鎖冷卻中、還剩多久。這個狀態檔本身由各腳本
    自己讀寫，這裡只負責「讀出來呈現」，不負責產生內容。"""
    path = DATA_DIR / "rate_limit_state.json"
    if not path.exists():
        return {"note": "尚未有任何腳本觸發過rate_limit_state.json（沒有請求記錄，也沒有被封鎖過）"}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"note": f"讀取rate_limit_state.json失敗：{e}"}
    now = datetime.now(timezone.utc).timestamp()
    sources = {}
    for name, src in state.get("sources", {}).items():
        blocked_until = src.get("blocked_until")
        is_blocked = bool(blocked_until and now < blocked_until)
        sources[name] = {
            "blocked": is_blocked,
            "blocked_remaining_min": round((blocked_until - now) / 60, 1) if is_blocked else None,
            "block_reason": src.get("block_reason") if is_blocked else None,
            "blocked_at": src.get("blocked_at") if is_blocked else None,
        }
    return {
        "note": "各資料源目前的請求節流/斷路狀態（≥3秒間隔+收到428/403封鎖2小時，"
                "2026-08-28新增，見BACKLOG.md「資料源禮儀」）。blocked=true代表目前"
                "所有腳本都會拒絕對這個來源發送請求，不是故障，是主動禮讓。",
        "sources": sources,
    }


def main():
    payload = {
        "updated_at": datetime.now(TW_TZ).isoformat(),
        "latest_commit": _git("rev-parse", "--short", "HEAD"),
        "data_files": build_data_files(),
        "workflows": build_workflows(),
        "app_data_sources": APP_DATA_SOURCES,
        "field_fallback_chains": FIELD_FALLBACK_CHAINS,
        "rate_limit_status": build_rate_limit_status(),
        "todo": TODO,
        "known_limitations": KNOWN_LIMITATIONS,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}")
    print(f"latest_commit={payload['latest_commit']}，data_files={len(payload['data_files'])}筆，workflows={len(payload['workflows'])}筆")


if __name__ == "__main__":
    main()
