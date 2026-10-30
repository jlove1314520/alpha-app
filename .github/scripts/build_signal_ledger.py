# -*- coding: utf-8 -*-
"""B19 訊號管線骨架：把 L1 重大訊息／L3 媒體新聞【事前】寫進 data/signal_ledger.json。

規格：research/B19_SIGNAL_LEDGER_SPEC.md（2026-10-11 事前登記，adeb12243）。

鐵律（BACKLOG B19 第 4 點）：訊號只能事前寫入、不得事後補建。實作上靠兩道防線：
1. 新鮮度窗：只收事件日 >= 今天(台北) − FRESH_DAYS 的事件，第一次跑或停擺後恢復
   都不會把 events.json 裡 90 天的舊事件一次補建進來。
2. append-only：ID 已存在就整筆跳過，不覆寫任何欄位（回填由
   update_signal_ledger_returns.py 負責，且只填 null 欄位）。

分層、交叉驗證、已反映偵測的定義與參數全照規格第 1～3 節，不在這裡另調。
"""
from __future__ import annotations

import hashlib
import json
import sys as _phs_sys  # 先.八十二-1：price_history 改拆檔（data/price_history/），讀寫一律走 scripts/price_history_store.py
from pathlib import Path as _phs_Path
_phs_sys.path.insert(0, str(_phs_Path(__file__).resolve().parents[2] / "scripts"))
import price_history_store as PHS  # noqa: E402
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception as e:  # 主控台不支援 reconfigure 時照常跑，只是特殊字元可能顯示不全
    print(f"[build_signal_ledger] stdout reconfigure 失敗（不中止）：{e}")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LEDGER_PATH = REPO_ROOT / "data" / "signal_ledger.json"
EVENTS_PATH = REPO_ROOT / "data" / "events.json"
NEWS_PATH = REPO_ROOT / "data" / "news.json"
PRICE_HISTORY_PATH = REPO_ROOT / "data" / "price_history.json"
TW_TZ = timezone(timedelta(hours=8))

FRESH_DAYS = 4            # 規格第 4 節：唯一的新增參數
XVAL_WINDOW_DAYS = 3      # 規格第 2 節
RUN_BEFORE_DAYS = 5       # 設計小抄第三節
RUN_BEFORE_CAUTION = 0.15
VOL_AVG_DAYS = 20
PRE_VOL_SPIKE = 2.0
STALE_DAYS_THRESHOLD = 10  # 跟 build_picks_ledger.py 同一套進場價過期門檻

L1_TYPES = {"重大訂單", "併購", "處分資產", "增減資", "財務", "訴訟", "法說會"}
L1_SOURCES = {"TWSE 重大訊息", "TPEx 重大訊息"}


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"讀 {path} 失敗（不中止，視為空）：{e}")
        return {}


def _independent_source(name: str) -> str:
    # 經濟日報三個 RSS（焦點／產業／證券）是同一家媒體，只算一個獨立來源
    return "經濟日報" if name.startswith("經濟日報") else name


def _news_date(published: str) -> str | None:
    try:
        return parsedate_to_datetime(published).astimezone(TW_TZ).strftime("%Y-%m-%d")
    except Exception:
        return None


def _sig_id(layer: str, source: str, code: str, date: str, title: str) -> str:
    raw = "|".join([layer, source, code, date, title])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _collect_candidates(events: list[dict], news: list[dict]) -> list[dict]:
    out = []
    for e in events:
        if e.get("source") in L1_SOURCES and e.get("type") in L1_TYPES and e.get("code") and e.get("date"):
            out.append({"layer": "L1", "source": e["source"], "source_id": e.get("url", ""),
                        "type": e["type"], "code": e["code"], "event_date": e["date"],
                        "title": e.get("title", "")})
    for n in news:
        d = _news_date(n.get("published", ""))
        if not d:
            continue
        for code in n.get("codes") or []:
            out.append({"layer": "L3", "source": n.get("source", ""), "source_id": n.get("url", ""),
                        "type": "媒體報導", "code": code, "event_date": d, "title": n.get("title", "")})
    return out


def _days_apart(a: str, b: str) -> int:
    return abs((datetime.strptime(a, "%Y-%m-%d") - datetime.strptime(b, "%Y-%m-%d")).days)


def _cross_validate(c: dict, all_l1_events: list[dict], news_cands: list[dict]) -> dict:
    """規格第 2 節 (a)(b)；(c) 自有資料佐證本版未實作，誠實標 not_implemented。"""
    l1_match = c["layer"] in ("L1", "L2") or any(
        e["code"] == c["code"] and _days_apart(e["date"], c["event_date"]) <= XVAL_WINDOW_DAYS
        for e in all_l1_events)
    srcs = sorted({_independent_source(n["source"]) for n in news_cands
                   if n["code"] == c["code"] and _days_apart(n["event_date"], c["event_date"]) <= XVAL_WINDOW_DAYS})
    return {"l1_l2_corroborated": bool(l1_match), "independent_l3_sources": srcs,
            "own_data": "not_implemented"}


def _reflected(code: str, event_date: str, prices: dict) -> dict:
    rows = [r for r in prices.get(code, []) if r.get("close") is not None and r["date"] <= event_date]
    need = max(RUN_BEFORE_DAYS, VOL_AVG_DAYS + 2) + 1
    if len(rows) < need:
        return {"run_before": None, "pre_vol_spike": None, "reflected": "unknown",
                "pre_volume_spike": None, "reason": f"價格序列不足（{len(rows)}<{need} 筆）"}
    d = rows[-1]
    run_before = d["close"] / rows[-1 - RUN_BEFORE_DAYS]["close"] - 1
    base = [r.get("volume") or 0 for r in rows[-3 - VOL_AVG_DAYS:-3]]
    avg = sum(base) / len(base) if base else 0
    pre = max(rows[-2].get("volume") or 0, rows[-3].get("volume") or 0)
    spike = (pre / avg) if avg > 0 else None
    pre_flag = bool(spike is not None and spike > PRE_VOL_SPIKE)
    caution = run_before > RUN_BEFORE_CAUTION
    return {"run_before": round(run_before, 4), "pre_vol_spike": round(spike, 3) if spike is not None else None,
            "reflected": "caution" if caution else "fresh", "pre_volume_spike": pre_flag,
            "anchor_trade_date": d["date"]}


def _ref_price(code: str, today: str, prices: dict) -> tuple[float | None, str | None]:
    """寫入當下已知的最新收盤，只當參考（看寫入時價位），不拿來算報酬——它可能早於事件本身
    （週末寫入時是上週收盤），用它當進場價會把事件反應算進報酬，是前視。進場價由回填腳本
    取「寫入日之後第一個交易日收盤」，見規格第 4 節。"""
    rows = [r for r in prices.get(code, []) if r.get("close") is not None and r["date"] <= today]
    if not rows:
        return None, None
    best = rows[-1]
    if _days_apart(today, best["date"]) > STALE_DAYS_THRESHOLD:
        return None, None
    return best["close"], best["date"]


def main() -> None:
    now = datetime.now(TW_TZ)
    today = now.strftime("%Y-%m-%d")
    cutoff = (now - timedelta(days=FRESH_DAYS)).strftime("%Y-%m-%d")

    events = _load_json(EVENTS_PATH).get("events", [])
    news = _load_json(NEWS_PATH).get("news", [])
    try:
        prices = PHS.load(PRICE_HISTORY_PATH).get("prices", {})
    except Exception as e:  # noqa: BLE001
        # 先.一三五-1cl：價格檔讀不出來就不寫檔（原本拋未處理例外）
        raise SystemExit(f"讀 {PRICE_HISTORY_PATH} 失敗，本輪不寫 signal_ledger.json：{e}")
    for rows in prices.values():
        rows.sort(key=lambda r: r["date"])

    # 先.一三五-1cl：既有台帳存在但讀不出來／結構不對時，原本當成空台帳、用「只有本輪新訊號」的檔整份覆寫歷史（不可逆）
    ledger = {}
    if LEDGER_PATH.exists():
        try:
            ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            raise SystemExit(f"既有 {LEDGER_PATH} 讀不出來，本輪不寫檔以免覆寫歷史訊號：{e}")
        if not isinstance(ledger, dict) or not isinstance(ledger.get("signals", []), list):
            raise SystemExit(f"既有 {LEDGER_PATH} 結構不對（不是物件或 signals 不是陣列），本輪不寫檔")
    meta = ledger.setdefault("meta", {})
    meta.setdefault("created_at", now.isoformat())
    meta["schema_note"] = ("B19 前瞻訊號台帳（非回測）：每筆在事件發生後 4 日內事前寫入，寫入後內容不可修改；entry_close 為寫入日之後第一個交易日收盤（避免前視）；"
                           "returns.t5/t20/t60 由 update_signal_ledger_returns.py 只回填 null 欄位。"
                           "status=待驗證線索 者不得影響任何評分。規格 research/B19_SIGNAL_LEDGER_SPEC.md。非投資建議。")
    signals = ledger.setdefault("signals", [])
    seen = {s["id"] for s in signals}

    cands = _collect_candidates(events, news)
    all_l1 = [e for e in events if e.get("source") in L1_SOURCES and e.get("code")]
    news_cands = [c for c in cands if c["layer"] == "L3"]

    added = skipped_old = 0
    for c in cands:
        if c["event_date"] < cutoff or c["event_date"] > today:
            skipped_old += 1
            continue
        sid = _sig_id(c["layer"], c["source"], c["code"], c["event_date"], c["title"])
        if sid in seen:
            continue
        xv = _cross_validate(c, all_l1, news_cands)
        promoted = xv["l1_l2_corroborated"] or len(xv["independent_l3_sources"]) >= 2
        refl = _reflected(c["code"], c["event_date"], prices)
        ref_close, ref_date = _ref_price(c["code"], today, prices)
        weight = 0.5 if (refl["reflected"] == "caution" or refl.get("pre_volume_spike")) else 1.0
        signals.append({
            "id": sid, "recorded_at": now.isoformat(), **c,
            "status": "訊號" if promoted else "待驗證線索",
            "cross_validation": xv, **refl, "weight": weight,
            "ref_close": ref_close, "ref_close_date": ref_date,
            "entry_rule": "寫入日之後第一個交易日收盤（回填腳本只填一次）",
            "entry_close": None, "entry_date": None,
            "returns": {"t5": None, "t20": None, "t60": None},
        })
        seen.add(sid)
        added += 1

    meta["last_build_at"] = now.isoformat()
    meta["total_signals"] = len(signals)
    meta["source"] = ".github/scripts/build_signal_ledger.py（讀 events.json L1＋news.json L3＋price_history.json）"
    LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    by = {}
    for s in signals:
        by[s["status"]] = by.get(s["status"], 0) + 1
    print(f"signal_ledger：本輪新增 {added} 筆（新鮮度窗外跳過 {skipped_old} 筆候選），累計 {len(signals)} 筆 {by}")


if __name__ == "__main__":
    main()
