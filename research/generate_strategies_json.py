# -*- coding: utf-8 -*-
"""策略監控台資料產生腳本（2026-08-29新增，使用者原話「把『盲目相信CC餵的
結果』變成『親眼看到每個策略的狀態』」）。

**鐵律（使用者明確裁示，這支腳本存在的唯一理由）**：`data/strategies.json`
100%由這支腳本從真實檔案（`scores*.json`、`data/picks_ledger.json`、
`research/TRIALS_LEDGER.md`、`research/B24_RESULTS.md`）推導產生，**不得
手寫任何策略的status/績效數字**。找不到來源檔就是`null`／狀態「尚未」，
不得樂觀假設。每個策略的`status`欄位都必須能回答「這個判定是從哪個檔案、
哪一段內容推出來的」，不能是憑印象填的。

**status優先序（本腳本的判斷邏輯，五個狀態互斥，取最高優先序符合的那個，
下面由高到低）**：
1. `回測通過`/`回測未通過`——`B24_RESULTS.md`存在且該策略有對應結果區塊時，
   最高優先（最嚴謹的證據）。及格判定：TRAIN跟VALIDATION兩期都「策略報酬
   >買進持有」且alpha顯著（p<0.05），兩者缺一即不及格——跟App選股頁「本榜
   為資料排序，尚未經過組合策略回測驗證」那行字掛不掛牌是同一把尺。
2. `回測中`——沒有`B24_RESULTS.md`/結果CSV，但偵測到對應的PIT回測背景
   log檔案存在且最近幾小時內有更新（推斷有回測正在跑，不是100%可靠的
   偵測，只能靠檔案時間戳這種間接證據，誠實揭露這個侷限）。
3. `紙上交易中`——`data/picks_ledger.json`裡有這個板的快照記錄。
4. `規格完成`——有對應的正式上線評分引擎（`scores*.json`存在且有
   `meta.generated_at`）。
5. `草稿`——以上都沒有。

跑法：`python generate_strategies_json.py`，寫出`data/strategies.json`。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
OUT_PATH = DATA_DIR / "strategies.json"

TRIALS_LEDGER_PATH = RESEARCH_DIR / "TRIALS_LEDGER.md"
B24_RESULTS_PATH = RESEARCH_DIR / "B24_RESULTS.md"
PICKS_LEDGER_PATH = DATA_DIR / "picks_ledger.json"
PRICE_HISTORY_PATH = DATA_DIR / "price_history.json"

# 三榜各自的PIT回測背景log檔案（見run_value_board_v2_pit_backtest.py等），
# 用來偵測「回測中」——只有價值成長榜目前有對應的回測腳本在跑，題材動能/
# 未來性濾網兩榜連腳本都還沒有（見下方LIMITATIONS常數的說明），log路徑
# 留空代表「這個板目前不可能處於回測中狀態，因為連回測腳本都不存在」。
BACKTEST_LOG_PATHS = {
    "value": RESEARCH_DIR / "pit_run_liquidity500_full.log",
    "momentum": None,
    "future": None,
}
BACKTEST_IN_PROGRESS_STALE_HOURS = 12  # log超過這個時數沒更新，不算「回測中」，避免誤報陳年log


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _mtime_iso(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).astimezone().isoformat()


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 -- 讀壞的來源檔誠實回報None，不假裝有資料
        print(f"  [警告] 讀取{path}失敗：{e}")
        return None


def parse_fut_trials() -> dict:
    """從`TRIALS_LEDGER.md`動態算FUT軌試驗數與是否有任何乾淨PASS——不
    hardcode「22個」這種數字，避免這份帳本之後又新增列時這裡沒同步更新
    造成的資料不一致（這支腳本本身要示範「不寫死」的紀律）。"""
    text = TRIALS_LEDGER_PATH.read_text(encoding="utf-8") if TRIALS_LEDGER_PATH.exists() else None
    if text is None:
        return {"n_tested": None, "n_passed": None, "has_pass": None, "source": None}
    rows = re.findall(r"^\|\s*\d+\s*\|.*\|\s*FUT\s*\|.*$", text, re.MULTILINE)
    n_tested = len(rows)
    n_passed = 0
    for row in rows:
        cols = row.split("|")
        verdict = cols[7].strip() if len(cols) > 7 else ""
        # 乾淨的PASS一律是`**PASS**`（跟`CHEAP_PASS`/`EXPERIMENTAL`/`FAIL`
        # 用詞不同，見TRIALS_LEDGER.md既有慣例），CHEAP_PASS/EXPERIMENTAL
        # 都不算「通過統計驗證」，這裡故意排除掉。
        if "**PASS**" in verdict:
            n_passed += 1
    return {
        "n_tested": n_tested, "n_passed": n_passed, "has_pass": n_passed > 0,
        "source": "research/TRIALS_LEDGER.md（動態解析FUT軌列數，非寫死數字）",
    }


def parse_b24_results(board_key: str) -> dict | None:
    """`B24_RESULTS.md`預期格式（這支腳本自己定義、由回測完成後另外寫入）：
    每個板一個` ## <board_key>`標題，後面緊跟一個fenced ```json區塊，內容
    是`{train:{...}, validation:{...}, pass:bool, criteria:"..."}`——用JSON
    區塊而不是解析散文/表格，避免格式一改這裡就解析失敗。目前這個檔案還
    不存在（B24-500回測背景中，尚未跑完），回傳None。"""
    if not B24_RESULTS_PATH.exists():
        return None
    text = B24_RESULTS_PATH.read_text(encoding="utf-8")
    m = re.search(rf"##\s*{re.escape(board_key)}\s*\n+```json\s*\n(.*?)\n```", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception as e:  # noqa: BLE001
        print(f"  [警告] B24_RESULTS.md的{board_key}區塊JSON解析失敗：{e}")
        return None


def backtest_field_from_b24(parsed: dict | None) -> dict | None:
    if parsed is None:
        return None
    tr, va = parsed.get("train", {}), parsed.get("validation", {})
    return {
        "年化報酬_train_pct": tr.get("return_pct"), "年化報酬_validation_pct": va.get("return_pct"),
        "sharpe原始": va.get("sharpe_raw"), "sharpe_x0.5": va.get("sharpe_x05"), "sharpe_x0.7": va.get("sharpe_x07"),
        "cvar95_日pct": va.get("cvar_95_daily_pct"), "勝率pct": va.get("win_rate_pct"),
        "mdd_pct": va.get("mdd_pct"), "sortino": va.get("sortino"),
        "翻倍率pct": va.get("moonshot_rate"), "地雷率pct": va.get("mine_rate"),
        "隨機對照百分位": va.get("random_control_percentile"), "隨機對照draws次數": va.get("random_draws"),
        "alpha_p值": va.get("alpha_pvalue"), "alpha顯著": va.get("alpha_significant"),
        "期間": f"{tr.get('start')}~{va.get('end')}（TRAIN {tr.get('start')}~{tr.get('end')}，VALIDATION {va.get('start')}~{va.get('end')}）",
        "來源檔": "research/B24_RESULTS.md",
    }


def backtest_in_progress(board_key: str) -> bool:
    log_path = BACKTEST_LOG_PATHS.get(board_key)
    if log_path is None or not log_path.exists():
        return False
    age_hours = (datetime.now().timestamp() - log_path.stat().st_mtime) / 3600
    return age_hours <= BACKTEST_IN_PROGRESS_STALE_HOURS


def paper_field(board_key: str) -> dict | None:
    """`data/picks_ledger.json`裡這個板的快照——「至今報酬」用最早一次
    快照的Top20收盤價 vs `data/price_history.json`目前最新收盤價，等權
    平均算未實現報酬（不重新平衡、不計成本，是最簡單的「如果那天買進
    抱到現在」估計，不是嚴謹回測，這個簡化寫進limitations裡）。"""
    ledger = _load_json(PICKS_LEDGER_PATH)
    if ledger is None:
        return None
    snapshots = [s for s in ledger.get("snapshots", []) if s.get("board") == board_key]
    if not snapshots:
        return None
    snapshots.sort(key=lambda s: s.get("snapshot_date", ""))
    first = snapshots[0]

    price_history = _load_json(PRICE_HISTORY_PATH)
    prices = (price_history or {}).get("prices", {})

    rets = []
    for p in first.get("picks", []):
        code, entry_price = p.get("code"), p.get("close_price")
        if entry_price in (None, 0):
            continue
        rows = prices.get(code)
        if not rows:
            continue
        latest = sorted(rows, key=lambda r: r["date"])[-1]
        latest_close = latest.get("adj_close") or latest.get("close")
        if latest_close in (None, 0):
            continue
        rets.append(latest_close / entry_price - 1)

    avg_ret_pct = round(sum(rets) / len(rets) * 100, 2) if rets else None
    return {
        "起始日": first.get("snapshot_date"),
        "快照數": len(snapshots),
        "至今報酬pct": avg_ret_pct,
        "至今報酬樣本數": f"{len(rets)}/{len(first.get('picks', []))}（有些pick快照當時價格缺失，如實排除不補值）",
        "來源": "data/picks_ledger.json",
        "計算方式": "等權、不重新平衡、不計成本的未實現報酬估計（最早快照收盤價 vs 目前最新收盤價），非嚴謹回測",
    }


def scores_meta(scores_filename: str) -> dict | None:
    path = REPO_ROOT / scores_filename
    d = _load_json(path)
    if d is None:
        return None
    return d.get("meta", {})


def build_strategy(
    strategy_id: str, name: str, stype: str, spec: str,
    scores_filename: str | None, board_key: str | None,
    limitations: list[str], extra: dict | None = None,
) -> dict:
    meta = scores_meta(scores_filename) if scores_filename else None
    b24 = parse_b24_results(board_key) if board_key else None
    backtest = backtest_field_from_b24(b24)
    paper = paper_field(board_key) if board_key else None
    in_progress = backtest_in_progress(board_key) if board_key else False

    if backtest is not None:
        status = "回測通過" if b24.get("pass") else "回測未通過"
    elif in_progress:
        status = "回測中"
    elif paper is not None:
        status = "紙上交易中"
    elif meta is not None:
        status = "規格完成"
    else:
        status = "草稿"

    last_updated_candidates = [
        _mtime_iso(REPO_ROOT / scores_filename) if scores_filename else None,
        _mtime_iso(B24_RESULTS_PATH) if backtest is not None else None,
        _mtime_iso(PICKS_LEDGER_PATH) if paper is not None else None,
    ]
    last_updated_candidates = [t for t in last_updated_candidates if t]
    last_updated = max(last_updated_candidates) if last_updated_candidates else None

    out = {
        "id": strategy_id, "name": name, "type": stype, "status": status,
        "spec": spec, "backtest": backtest, "paper": paper,
        "limitations": limitations, "last_updated": last_updated,
    }
    if extra:
        out.update(extra)
    return out


def build_futures_track() -> dict:
    trials = parse_fut_trials()
    if trials["n_tested"] is None:
        status = "草稿"
    elif trials["has_pass"]:
        status = "回測通過"
    else:
        status = "回測未通過"
    return {
        "id": "fut_track", "name": "期貨軌（TAIFEX台指期策略假說）", "type": "期貨",
        "status": status,
        "spec": "台指期連續合約 + 因子/策略假說掃描（fut_cheap_gate.py配對式隨機控制組200次排列）",
        "backtest": None,  # 這是逐假說的篩選帳本，不是單一組合策略的backtest指標組，故意留null
        "paper": None,  # picks_ledger.json目前沒有futures板的快照
        "trials_summary": {
            "已測試假說數": trials["n_tested"], "通過統計驗證數": trials["n_passed"],
            "來源": trials["source"],
        },
        "limitations": [
            f"截至本次產生，已測試{trials['n_tested']}個策略假說，全部未通過統計驗證關卡"
            if trials["n_tested"] and not trials["has_pass"] else "見trials_summary",
            "這不是「還沒開始做」，是誠實做過完整的配對式隨機控制組檢定，目前確實還沒找到站得住腳的訊號",
            "數字動態從research/TRIALS_LEDGER.md算出，不是寫死的——之後這份帳本增列，這裡會自動更新",
        ],
        "last_updated": _mtime_iso(TRIALS_LEDGER_PATH),
    }


def build_draft_baseline(strategy_id: str, name: str, stype: str, spec: str, limitations: list[str]) -> dict:
    """2026-08-29新增（使用者「少走彎路指南」item六：登錄兩個新baseline
    候選，狀態=草稿/待回測，先只登錄規格不執行）。這兩個策略目前**完全
    沒有實作**（沒有對應的scores*.json/backtest/paper任何來源檔），
    `草稿`是唯一誠實的狀態——不透過`build_strategy()`那套「從檔案推導」
    的邏輯（沒有檔案可推導），直接宣告草稿本身沒有違反「不寫死樂觀值」
    的鐵律，因為草稿是最保守、最低的狀態，不是樂觀假設。"""
    return {
        "id": strategy_id, "name": name, "type": stype, "status": "草稿",
        "spec": spec, "backtest": None, "paper": None,
        "limitations": limitations, "last_updated": _now_iso(),
    }


def main():
    strategies = [
        build_strategy(
            strategy_id="value_board_v2", name="價值成長榜", stype="選股",
            spec="score_v2.py 八大因子（估值/成長/品質/動能等），App選股頁正式上線引擎",
            scores_filename="scores.json", board_key="value",
            limitations=[
                "JSON-only上線路徑（generate_scores_live.py）覆蓋率上限約0.74"
                "（technical/analyst/catalyst三項恆缺，見data/STATUS.json todo）",
                "B24-500全樣本PIT回測：隨機對照組原目標1000次draws，實測後誠實降級為100次"
                "（實測約102秒/draw，1000次×2期間需約70小時不可行，見run_value_board_v2_pit_backtest.py）",
            ],
        ),
        build_strategy(
            strategy_id="momentum_board", name="題材動能榜", stype="選股",
            spec="generate_scores_momentum.py 十大因子（相對強度/量價配合度/籌碼集中度等），"
                 "App選股頁正式上線引擎",
            scores_filename="scores_momentum.json", board_key="momentum",
            limitations=[
                "尚無PIT回測引擎——generate_scores_momentum.py是JSON-only上線評分路徑，讀"
                "「即時累積快照」（data/price_history.json目前僅90天），不是TRIALS_LEDGER.md"
                "既有框架用的load_dev()歷史parquet資料（2010-2024train/val切分）",
                "要做歷史回測，第一步得先建一套「用歷史FinMind快取重算這10個新因子」的管線"
                "（比照factors.py::prepare_factors()模式），工作量不小於這支JSON-only腳本本身"
                "（見TRIALS_LEDGER.md「待測」章節2026-08-27條目）",
            ],
        ),
        build_strategy(
            strategy_id="future_board", name="未來性濾網", stype="選股",
            spec="generate_scores_future.py 五大因子（法人籌碼行為/毛利率品質/產能利用率代理等），"
                 "App選股頁正式上線引擎",
            scores_filename="scores_future.json", board_key="future",
            limitations=[
                "尚無PIT回測引擎，跟題材動能榜同一個缺口（見上方momentum_board的limitations，"
                "同一份TRIALS_LEDGER.md記錄涵蓋兩榜）",
                "customer_concentration（營收客戶集中度）因子未實作，沒有現成免費資料源，誠實留白",
            ],
        ),
        build_futures_track(),
        build_draft_baseline(
            strategy_id="weinstein_stage2_baseline", name="Weinstein第二階段掃描（股票baseline候選）",
            stype="選股",
            spec="站上30週均線 + 均線上揚 + 相對強弱——股票最自然的baseline，"
                 "尚未實作（跟research/strategies/weinstein_stage2.py既有的backtest基礎設施"
                 "同名但不同東西：那是回測引擎沿用的market-regime prepare函式，不是這個策略本身）",
            limitations=[
                "2026-08-29使用者裁示登錄，只登錄規格不執行，回測排在B24-500之後",
                "TRIALS_LEDGER.md#10/#11已有較早的weinstein_stage2試點記錄（手選30檔試點FAIL、"
                "無偏宇宙+配對式對照組版EXPERIMENTAL），這個新baseline候選要重新設計，不是重跑舊版",
            ],
        ),
        build_draft_baseline(
            strategy_id="cta_trend_following_baseline", name="CTA趨勢跟隨（期貨baseline候選，時序動量）",
            stype="期貨",
            spec="時序動量（time-series momentum）——期貨最該先做的一條baseline，獨立跑，"
                 "尚未實作",
            limitations=[
                "2026-08-29使用者裁示登錄，只登錄規格不執行，回測排在B24-500之後",
                "跟TRIALS_LEDGER.md已測過的#18`fut_trend_multi_tf`（10/20/60日動能訊號多數決）"
                "不是同一個東西——那是截面/多時間框架訊號的組合判定，這裡要做的是經典CTA式"
                "單一時序動量（例如12個月回顧報酬正負號），設計上更接近學術文獻的標準定義，"
                "不能直接沿用#18已FAIL的結論當作這個新候選也會失敗的證據",
            ],
        ),
    ]

    payload = {
        "generated_at": _now_iso(),
        "note": "本頁面/檔案所有數字僅供研究參考，非投資建議。狀態欄位100%由本腳本從真實檔案"
                "（scores*.json/data/picks_ledger.json/research/TRIALS_LEDGER.md/"
                "research/B24_RESULTS.md）推導，找不到來源檔一律顯示null/尚未，不寫死樂觀值。",
        "strategies": strategies,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}")
    for s in strategies:
        print(f"  {s['id']}: status={s['status']}")


if __name__ == "__main__":
    main()
