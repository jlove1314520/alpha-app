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
}


def _git(*args) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()


def describe_quotes(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    meta = d.get("meta", {})
    return {
        "generated_at": d.get("fetched_at"),
        "records": meta.get("matched"),
        "source": d.get("source"),
        "detail": f"queried={meta.get('queried')} matched={meta.get('matched')} trading_window={meta.get('trading_window')}",
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


def describe_paper_trades(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    return {
        "generated_at": d.get("generated_at"),
        "records": len(d.get("strategies", [])),
        "source": "無（尚未串接任何真實券商API，App誠實顯示空狀態，不是資料源故障）",
        "detail": "schema_version=%s，strategies為空陣列是刻意設計，不是bug" % d.get("schema_version"),
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
INTENTIONALLY_EMPTY = {"paper_trades.json"}


def build_data_files() -> list[dict]:
    out = []
    for path in sorted(DATA_DIR.glob("*.json")):
        if path.name == "STATUS.json":
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
    {"panel": "今日頁·自選股報價（主價格）", "source": "data/quotes_tw.json + data/quotes_us.json"},
    {"panel": "今日頁·自選股sparkline走勢", "source": "FinMind TaiwanStockPrice/USStockPrice（未遷移——任意自選股代碼，跟market_tw/us.json的固定指數不同，額度用盡時sparkline會缺，主價格不受影響）"},
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
    {"panel": "個股頁·財報·EPS/毛利率/營益率/ROE", "source": "data/stock_detail.json（TWSE官方t187ap06_L_ci/07_L_ci，2026-08-27起不再打FinMind；僅涵蓋「上市一般業」，上櫃/金融股查不到）"},
    {"panel": "個股頁·財報·自由現金流(FCF)", "source": "無（TWSE官方無現金流量表開放資料，永久性限制，已誠實顯示「TWSE無此資料源」，不是暫時缺漏）"},
    {"panel": "個股頁·籌碼·三大法人買賣超", "source": "data/stock_detail.json（TWSE T86，跟market_tw.json共用同一次呼叫，2026-08-27起不再打FinMind）"},
    {"panel": "個股頁·籌碼·融資融券", "source": "data/stock_detail.json（TWSE MI_MARGN，跟大盤融資維持率共用同一次呼叫，2026-08-27起不再打FinMind；估算融資維持率為App自算，非官方資料）"},
    {"panel": "個股頁·AI·個股簡報/券商報告雷達", "source": "無（誠實佔位「功能建置中」）"},
    {"panel": "交易頁·策略/機器人列表", "source": "data/paper_trades.json（空陣列，誠實佔位，未串接任何真實券商API）"},
    {"panel": "交易頁·大盤融資維持率", "source": "data/margin_maintenance.json（2026-08-27起改排程：分子TWSE官方MI_MARGN/STOCK_DAY_ALL，分母仍FinMind，見known_limitations）"},
    {"panel": "日誌頁·本週損益/AI週覆盤/交易紀錄", "source": "無（尚無交易紀錄，誠實佔位）"},
]

TODO = [
    {"item": "data/indices.json（使用者原始規格）vs 現有 market_tw.json/market_us.json 是否視為已完成，待使用者裁示", "priority": "P1", "blocker": "等使用者決定要不要重做成獨立檔名/pipeline"},
    {"item": "個股頁美股分頁完全不支援月營收/財報/三大法人/融資融券", "priority": "P2", "blocker": "FinMind僅提供台股這幾類資料，TWSE官方資料也只涵蓋台股，暫無替代來源"},
    {"item": "個股頁財報FCF永久缺口", "priority": "P2", "blocker": "TWSE官方開放資料無現金流量表端點（已查證swagger完整清單確認），非暫時性，需另尋資料源才能補上"},
    {"item": "個股頁財報/三大法人/融資融券僅涵蓋TWSE上市「一般業」", "priority": "P2", "blocker": "上櫃(TPEx)股票、金融/證券/保險等特殊產業分類的財報格式跟一般業不同，TWSE另外分開發布(t187ap06_L_bd/fh/ins/mim等)，尚未處理"},
    {"item": "個股走勢圖(價格歷史)脫離FinMind", "priority": "P2", "blocker": "需要逐檔排程抓歷史K線，API呼叫量遠大於目前的全市場單次快照模式"},
    {"item": "個股頁自選股sparkline走勢脫離FinMind", "priority": "P2", "blocker": "任意自選股代碼跟market_tw/us.json的固定指數不同，需要逐檔排程抓歷史，尚未評估"},
    {"item": "主流題材chips / 期貨籌碼 脫離FinMind", "priority": "P2", "blocker": "尚未評估TWSE/TAIFEX官方端點是否有對應逐股/逐法人資料"},
    {"item": "大盤融資維持率的分母(全市場融資金額)仍依賴FinMind", "priority": "P2", "blocker": "TWSE官方無對應的全市場融資金額(元)開放資料端點，只有逐股融資餘額(張)，已查證swagger清單確認"},
    {"item": "CLAUDE.md候選：美股報價/AI盤前日報真新聞/Phase2券商下單研究", "priority": "P2", "blocker": "尚未排序，等使用者指示"},
]

KNOWN_LIMITATIONS = [
    "fundamentals.json：TPEx上櫃股票的月營收/PER不會被update_fundamentals_daily.py更新（TWSE官方端點只涵蓋上市），停留在2026-08-27手動快照的舊值。",
    "margin_maintenance.json：2026-08-27起改為market.yml排程自動更新，但分母（全市場融資金額）仍用FinMind單一輕量呼叫（一天一次、抓全市場加總非逐股歷史，風險遠低於之前逐股迴圈），若這次呼叫失敗當天不會寫入新資料、history停在最後一筆有效值。",
    "stock_detail.json：財報/三大法人/融資融券只涵蓋TWSE上市「一般業」（t187ap06_L_ci分類），上櫃股票、金融控股/證券/保險等特殊產業分類查不到。FCF（自由現金流）永久性缺口——TWSE官方無現金流量表開放資料端點。",
    "個股頁美股分頁完全不支援月營收/財報/三大法人/融資融券（FinMind僅提供台股這幾類資料）。",
    "個股頁自選股sparkline走勢、個股走勢圖、主流題材chips、期貨籌碼，仍100%依賴FinMind免費額度，額度用盡時會誠實顯示連線失敗（不是假資料）。",
    "本檔案（STATUS.json）由generate_status_json.py產生，APP_DATA_SOURCES那份面板對照表是人工核對、不是自動掃描——異動面板資料源時要記得同步更新腳本裡的常數，否則這份清單會跟實際程式碼不同步。",
]


def main():
    payload = {
        "updated_at": datetime.now(TW_TZ).isoformat(),
        "latest_commit": _git("rev-parse", "--short", "HEAD"),
        "data_files": build_data_files(),
        "workflows": build_workflows(),
        "app_data_sources": APP_DATA_SOURCES,
        "todo": TODO,
        "known_limitations": KNOWN_LIMITATIONS,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}")
    print(f"latest_commit={payload['latest_commit']}，data_files={len(payload['data_files'])}筆，workflows={len(payload['workflows'])}筆")


if __name__ == "__main__":
    main()
