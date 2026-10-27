# -*- coding: utf-8 -*-
"""模擬 P：重大訂單／得標公告後漂移 前向紙上追蹤（先.一三六-B7）。

規則照 `docs/PREREG_ORDER_WIN_DRIFT_FORWARD_FINAL.md`（H＝20、M＝20；§5-1 乙＝判定日 2030-01-02，一次定死）；
共用部分在 research/paper_forward_common.py，本檔只有事件抽取＋訊號函式。
- 事件：source 含「重大訊息」、標題符合 INCLUDE、且不含 EXCLUDE 任一字；不用 type 欄。同代號 20 個交易日內只算第一則。
- t0＝公告日、t1＝t0 之後第一個交易日、t1 收盤買進；t0 前 20 個交易日均成交值 ≥1,000 萬；同日超額依代號排序；
  下市無後續價格以 −100% 計。
- 分類精準度稽核（資料品質關）：歸檔滿 60 個事件（t1 ≥ 起跑日）時 DevQueue 只看標題人工判定，結果寫
  research/data/paper_16_precision_audit.json（{"n":60,"correct":k,"precision":k/60,...}），<70% → DATA_DEFECT；
  本程式只讀這份檔、把狀態寫進摘要，不自動判。
資料：research/data/mops_events_archive.jsonl（scripts/archive_mops_events.py 長期歸檔）＋data/events.json 當下快照，
零額外外部請求。
"""
from __future__ import annotations

import json
import re

import paper_forward_common as C
import paper_forward_events as E

ROOT = C.ROOT
H, M = 20, 20
MIN_PRE_TURNOVER = 10_000_000.0
DEDUPE_DAYS = 20
AUDIT_N, AUDIT_MIN = 60, 0.70
START = "2027-01-04"
JUDGE = "2030-01-02"
PREREG = "docs/PREREG_ORDER_WIN_DRIFT_FORWARD_FINAL.md"
TRIAL_NO = 487  # register_trial() #487（2026-10-27 互動視窗 先.一三七-1 登記）
ARCHIVE = ROOT / "research" / "data" / "mops_events_archive.jsonl"
EVENTS = ROOT / "data" / "events.json"
AUDIT = ROOT / "research" / "data" / "paper_16_precision_audit.json"
INCLUDE = re.compile(r"(取得|接獲|簽訂|簽署|得標|承攬).{0,20}(訂單|採購案|標案|銷售合約|供貨合約|銷售契約|供貨契約|工程承攬|承攬契約|承攬案)|得標")
EXCLUDE = ("修正", "追加", "追減", "結束日", "更正", "關係人", "資安", "外洩", "轉換公司債", "澄清", "媒體", "報導",
           "取消", "解除", "終止", "延後", "訴訟", "通知")


def is_order_win(e: dict) -> bool:
    title = str(e.get("title") or "")
    return ("重大訊息" in str(e.get("source") or "") and bool(INCLUDE.search(title))
            and not any(w in title for w in EXCLUDE))


def load_all() -> list:
    rows = []
    try:
        for l in ARCHIVE.read_text(encoding="utf-8").splitlines():
            if l.strip():
                rows.append(json.loads(l))
    except (OSError, ValueError) as e:
        print(f"[warn] 模擬 P 讀歸檔失敗：{type(e).__name__}: {e}")
    snap = C.load_json(EVENTS, {}) or {}
    rows += snap.get("events") if isinstance(snap, dict) else (snap if isinstance(snap, list) else [])
    seen, out = set(), []
    for e in rows:
        k = (str(e.get("code")), e.get("date"), str(e.get("title") or "").strip())
        if k not in seen:
            seen.add(k)
            out.append(e)
    return out


def raw_events(rows: list, px: C.Px) -> list:
    out = [{"code": str(e["code"]), "t0": str(e["date"])[:10], "title": e.get("title")}
           for e in rows if e.get("code") and e.get("date") and C.is_common(str(e["code"])) and is_order_win(e)]
    return E.dedupe(out, px, DEDUPE_DAYS)


def audit_status(n_since_start: int) -> dict:
    a = C.load_json(AUDIT, None)
    if a and a.get("precision") is not None:
        return {"state": "DATA_DEFECT" if float(a["precision"]) < AUDIT_MIN else "PASSED", **a}
    return {"state": "PENDING", "events_since_start": n_since_start, "audit_at_n": AUDIT_N,
            "note": "滿 60 則時 DevQueue 只看標題人工判定（不得同時開價格或帳本），寫 research/data/paper_16_precision_audit.json"}


def make_signal(events: list):
    def signal(ctx: dict, day: str, uni: dict) -> list:
        px: C.Px = ctx["px"]
        prev = px.prev_trading_day(day)
        cands, skips = [], []
        for ev in events:
            if not ((prev is None or prev <= ev["t0"]) and ev["t0"] < day):
                continue  # 只收 t1（t0 之後第一個交易日）＝day 的事件
            code = ev["code"]
            if code not in uni:
                skips.append({"code": code, "reason": "不在宇宙（非普通股／不在市／t1 無收盤）"})
                continue
            liq = px.avg_turnover(code, ev["t0"], inclusive=False)
            if liq is None or liq < MIN_PRE_TURNOVER:
                skips.append({"code": code, "reason": "t0 前 20 日均成交值不足 1,000 萬或資料不滿 20 天"})
                continue
            cands.append({**ev, "pre_turnover_20d": round(liq)})
        cands.sort(key=lambda c: c["code"])
        ctx.setdefault("skips", {})[day] = skips
        return cands
    return signal


def spec(events: list) -> C.Spec:
    return C.Spec(key="paper_16", label="模擬 P 重大訂單／得標公告後漂移",
                  note="重大訊息標題為新取得訂單／得標者，公告後第一個交易日收盤買進、持有 20 個交易日；最多 20 檔、每筆淨值 1/20；成本 1×",
                  prereg=PREREG, trial_no=TRIAL_NO, start_not_before=START, judge_after=JUDGE, mode="event",
                  top_n=M, hold_days=H, delist_value="zero", signal=make_signal(events),
                  log_path=ROOT / "research" / "data" / "paper_16_log.jsonl", out_path=ROOT / "data" / "paper_16.json",
                  judge_text=("2030-01-02 後判一次（§5-1 乙，36 個月）：先過標題精準度稽核（60 則 ≥70%，否則 DATA_DEFECT）；"
                              "已平倉 ≥100 筆前提；天條一回撤 ≤50%；扣 1× 年化 > 0050 含息；2×／3× 成本年化 >0；"
                              "隨機時點對照 > 第 95 百分位（1,000 次、seed 20270104）"),
                  known_limit="營造／工程業得標占多數，可能是產業曝險而非公告效應（報告附產業分布）；標題規則 36 個月內不得改",
                  extra_summary={"events_source": "research/data/mops_events_archive.jsonl＋data/events.json"})


def step() -> dict:
    px = C.load_px()
    evs = raw_events(load_all(), px)
    n_since = sum(1 for e in evs if (px.next_trading_day(e["t0"]) or e["t0"]) >= START)
    extra = {"raw_events_after_dedupe": len(evs), "precision_audit": audit_status(n_since)}
    return C.step(spec(evs), {"px": px, "summary_extra": extra}, px=px)


if __name__ == "__main__":
    raise SystemExit(C.run_main(step, "模擬 P"))
