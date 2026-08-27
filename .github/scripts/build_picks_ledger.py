# -*- coding: utf-8 -*-
"""前瞻選股台帳（2026-08-28新增，B24第一步，使用者原話逐字照抄）：

「建立 data/picks_ledger.json：每日評分產出後，自動快照三榜各Top20（代號、
名稱、當日分數、當日收盤價、時間戳），排程在T+5/T+20/T+60/T+120回填實際
報酬與相對大盤超額。鐵律：只能事前快照，嚴禁事後補建（那是回測不是前瞻）。」

**這支腳本只做「快照」這一半，「回填」是另一支腳本
`update_picks_ledger_returns.py`（本輪先建骨架，見該檔案docstring）——兩者
分開是刻意的：快照本身是「今天已知的事實」，寫入後永遠不能被覆蓋或事後
修改內容（除非發現寫入時的技術性錯誤，例如格式錯誤，但分數/價格數字本身
一旦寫入就是歷史事實，不可回頭「校正」——這是使用者鐵律「只能事前快照，
嚴禁事後補建」的具體實作：`already_snapshotted()`保證同一個
(board, snapshot_date) 只會被快照一次，之後這支腳本重跑也不會覆蓋。

**掛進 `.github/workflows/market.yml`**：三榜(`generate_scores_live.py`/
`generate_scores_momentum.py`/`generate_scores_future.py`)產生完scores*.json
之後、commit之前執行——確保每天只要三榜跑過，當天的Top20快照就一定會被
記錄下來，不依賴我人工手動觸發。

**已知限制，誠實揭露**：
- Top20只計入`rank`不是null的股票（`rank=null`代表流動性不足/被排除在
  數字排名外，不該進「值得追蹤的選股」名單）。
- 收盤價來自`data/quotes_all_tw.json`（只有TWSE上市+部分上櫃，見該檔案
  既有已知限制），少數股票查不到收盤價的快照列會誠實記`close_price:null`，
  不會用其他不精確的價格頂替。
- 大盤基準用`data/market_tw.json`的taiex當下收盤（`taiex.close`欄位，
  非sparkline，避免依賴rolling window深度），一樣查不到就記null。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "picks_ledger.json"
TW_TZ = timezone(timedelta(hours=8))

BOARD_SCORE_FILES = {
    "value": REPO_ROOT / "scores.json",
    "momentum": REPO_ROOT / "scores_momentum.json",
    "future": REPO_ROOT / "scores_future.json",
}
QUOTES_ALL_TW_PATH = REPO_ROOT / "data" / "quotes_all_tw.json"
MARKET_TW_PATH = REPO_ROOT / "data" / "market_tw.json"
TOP_N = 20


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"讀 {path} 失敗（不中止，這個板塊今天就不快照）：{e}")
        return {}


def already_snapshotted(ledger: dict, board: str, snapshot_date: str) -> bool:
    """鐵律守門：同一個(board, snapshot_date)只能快照一次，重跑這支腳本不會
    覆蓋或重複寫入既有快照——這是「嚴禁事後補建」的具體實作。"""
    return any(s["board"] == board and s["snapshot_date"] == snapshot_date
               for s in ledger.get("snapshots", []))


def build_snapshot(board: str, score_path: Path, quotes: dict, taiex_close: float | None) -> dict | None:
    data = _load_json(score_path)
    if not data or not data.get("stocks"):
        print(f"  {board} 板：{score_path.name} 沒有資料，跳過")
        return None
    snapshot_date = data["meta"].get("data_asof")
    if not snapshot_date:
        print(f"  {board} 板：{score_path.name} 缺 meta.data_asof，跳過（不確定要記哪一天，寧可不記也不亂猜）")
        return None

    ranked = sorted(
        (s for s in data["stocks"] if s.get("rank") is not None),
        key=lambda s: s["rank"],
    )[:TOP_N]
    picks = []
    for s in ranked:
        code = s["code"]
        q = quotes.get(code) or {}
        price, price_date, stale = q.get("close"), q.get("date"), False
        # 2026-08-28新增（本機實測抓到的真案例：6452查到2020-08-17的收盤價，
        # 是quotes_all_tw.json/price_history.json對這檔股票的FinMind快取
        # 極度過期——跟B23發現的日曆缺口同一種根因，只是更嚴重）。「今日
        # 收盤價」若明顯不是今天附近的資料，寧可誠實記null，不要塞一個
        # 6年前的價格進去污染之後的報酬率計算。
        if price_date:
            try:
                age_days = (datetime.strptime(snapshot_date, "%Y-%m-%d")
                            - datetime.strptime(price_date, "%Y-%m-%d")).days
                if age_days > 10:
                    stale = True
            except ValueError:
                stale = True
        picks.append({
            "code": code, "name": s.get("name"),
            "rank": s["rank"], "total_score": s.get("total_score"),
            "close_price": None if stale else price,
            "price_date": None if stale else price_date,
            "price_stale": stale,
            "returns": {"t5": None, "t20": None, "t60": None, "t120": None},
        })
    return {
        "snapshot_date": snapshot_date,
        "taken_at": datetime.now(TW_TZ).isoformat(),
        "board": board,
        "engine_version": data["meta"].get("engine_version"),
        "taiex_close_at_snapshot": taiex_close,
        "picks": picks,
    }


def main():
    ledger = _load_json(OUT_PATH)
    ledger.setdefault("meta", {})
    ledger.setdefault("snapshots", [])
    ledger["meta"].setdefault("created_at", datetime.now(TW_TZ).isoformat())
    ledger["meta"]["schema_note"] = (
        "前瞻選股台帳（非回測）：每個snapshot是三榜其中一榜在某個data_asof的"
        "Top20快照，寫入後不可回頭修改內容（見already_snapshotted()）。"
        "returns.t5/t20/t60/t120由update_picks_ledger_returns.py（骨架，"
        "2026-08-28新增）在對應的未來交易日回填，回填前恆為null——App顯示"
        "時null代表「還沒到回填時間點」，不是資料遺失。"
    )

    quotes = _load_json(QUOTES_ALL_TW_PATH).get("quotes", {})
    market_tw = _load_json(MARKET_TW_PATH)
    taiex_close = (market_tw.get("taiex") or {}).get("close")

    added = 0
    for board, path in BOARD_SCORE_FILES.items():
        snap = build_snapshot(board, path, quotes, taiex_close)
        if not snap:
            continue
        if already_snapshotted(ledger, board, snap["snapshot_date"]):
            print(f"  {board} 板 {snap['snapshot_date']} 已經快照過，不重複寫入（鐵律：不事後補建/不覆蓋）")
            continue
        ledger["snapshots"].append(snap)
        added += 1
        print(f"  {board} 板 {snap['snapshot_date']}：快照 {len(snap['picks'])} 檔")

    ledger["meta"]["last_snapshot_at"] = datetime.now(TW_TZ).isoformat()
    ledger["meta"]["total_snapshots"] = len(ledger["snapshots"])
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"寫入 {OUT_PATH}：本輪新增 {added} 個快照，累計 {len(ledger['snapshots'])} 個")


if __name__ == "__main__":
    main()
