# -*- coding: utf-8 -*-
"""模擬 L：認購權證發行潮 前向紙上追蹤（先.一三二-5）。

規則照 `docs/PREREG_WARRANT_ISSUANCE_WAVE_FORWARD_FINAL.md`（W=20、M=20、R=60、做多，一次定死）；共用部分在
research/paper_forward_common.py，本檔只有：新發行出現日索引、起跑前提（快照連續 10 個交易日成功）、訊號函式。
- 新發行＝權證代號第一次出現在本機快照的那一天；首批快照（2026-10-14）已存在的權證沒有出現日。只算標的是普通股者。
  上市：掛牌名冊 basic_twse（cp＝認購、kind 以「一般型」開頭＝排除牛熊證）第一次出現——PREREG 修訂 R1（收件匣 033，
  2026-10-31）；原本用當日行情 quotes_twse_call，那份只列有成交的權證，會把「早已掛牌、第一次成交」誤記成新發行。
  basic_twse 的標的是名稱 → 先用同日 quotes_twse_call 的標的代號（同權證代號）對照，對不到再用 data/stock_names.json
  名稱對代號（同名多代號不採）；都對不到的照樣記出現日（標的記 null、不計入任何標的，每天筆數記在 unmapped_by_date），
  之後某天對得到才補標的、出現日不改——不然它會在對到那天被誤當新發行。上櫃 issue_tpex type=認購 的
  underlying_code 不變。
- 訊號：每月第一個交易日，標的過去 W 個交易日內出現的新認購權證檔數 S；S≥1 排前 M 進場（同分依近 20 日均成交值小到大、
  再依代號），跌出前 R 或 S=0 出場；W 個交易日內缺快照 >5 天 → 該月不調倉。
- 快照只在本機（research/data/warrant_snapshots/ 不進 repo）→ 本模擬只在本機跑（雲端沒有快照會停在 NOT_STARTED）。
零額外外部請求。
"""
from __future__ import annotations

import gzip
import json
from datetime import date
from pathlib import Path

import paper_forward_common as C

ROOT = C.ROOT
SNAP = ROOT / "research" / "data" / "warrant_snapshots"
APPEAR = ROOT / "research" / "data" / "paper_12_appearances.json"
NAMES = ROOT / "data" / "stock_names.json"
RULE_VERSION = "R1-basic_twse"  # 出現日索引規則版本；與檔內不同 → 從快照整份重建
W, M, R = 20, 20, 60
MAX_MISSING = 5
STREAK_NEED = 10
GATE_DEADLINE = "2026-11-30"
MIN_TURNOVER = 30_000_000.0
START = "2026-12-01"
JUDGE = "2028-12-01"
PREREG = "docs/PREREG_WARRANT_ISSUANCE_WAVE_FORWARD_FINAL.md"
TRIAL_NO = 466  # register_trial() 2026-10-23
SOURCES = ("basic_twse", "basic_tpex", "issue_tpex", "quotes_twse_call", "quotes_twse_put", "quotes_tpex", "underlying_tpex")


def snapshot_ok(d: str, snap: Path = SNAP) -> bool:
    p = snap / d
    return (p / "meta.json").exists() and all((p / f"{s}.json.gz").exists() for s in SOURCES)


def _gz(p: Path):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


_NAME2CODE: dict | None = None


def _name2code() -> dict:
    """台股名稱 → 代號（data/stock_names.json；同名多代號者不採）。讀不到回空表＝只靠同日行情對照。"""
    global _NAME2CODE
    if _NAME2CODE is None:
        seen: dict = {}
        for row in (C.load_json(NAMES, {}) or {}).get("tw") or []:
            if len(row) >= 2 and row[0] and row[1]:
                seen.setdefault(str(row[1]).strip(), set()).add(str(row[0]))
        _NAME2CODE = {n: next(iter(cs)) for n, cs in seen.items() if len(cs) == 1}
    return _NAME2CODE


def calls_in_detail(d: str, snap: Path = SNAP) -> tuple[dict, int]:
    """回傳 ({權證代號: 標的代號或 None（名冊標的對不到代號）}（只含一般型認購）, 對不到的筆數)。"""
    out = {}
    q_und = {str(r["code"]): str(r["underlying"]) for r in (_gz(snap / d / "quotes_twse_call.json.gz") or [])
             if r.get("code") and r.get("underlying")}
    n2c = _name2code()
    unmapped = 0
    for r in _gz(snap / d / "basic_twse.json.gz") or []:
        code = str(r.get("code") or "")
        if not code or r.get("cp") != "認購" or not str(r.get("kind") or "").startswith("一般型"):
            continue
        u = q_und.get(code) or n2c.get(str(r.get("underlying") or "").strip())
        out[code] = u
        unmapped += u is None
    for code, r in (_gz(snap / d / "issue_tpex.json.gz") or {}).items():
        if (r or {}).get("type") == "認購" and r.get("underlying_code"):
            out[str(code)] = str(r["underlying_code"])
    return out, unmapped


def calls_in(d: str, snap: Path = SNAP) -> dict:
    """回傳 {權證代號: 標的代號}（只含一般型認購、標的對得到代號者）。"""
    return {w: u for w, u in calls_in_detail(d, snap)[0].items() if u}


def update_appearances(snap: Path = SNAP, path: Path = APPEAR) -> dict:
    doc = C.load_json(path, {}) or {}
    if (doc.get("meta") or {}).get("rule_version") != RULE_VERSION:
        doc = {}  # 規則改版（PREREG 修訂 R1）→ 從快照整份重建
    seen = doc.get("warrants") or {}
    done = set(doc.get("dates_processed") or [])
    unmapped_by = doc.get("unmapped_by_date") or {}
    dates = sorted(p.name for p in snap.iterdir() if p.is_dir() and len(p.name) == 10 and p.name[4] == "-") if snap.exists() else []
    for d in dates:
        if d in done or not snapshot_ok(d, snap):
            continue
        first = not done
        calls, unmapped = calls_in_detail(d, snap)
        unmapped_by[d] = unmapped
        for w, u in calls.items():
            if w not in seen:
                seen[w] = {"first_seen": None if first else d, "underlying": u}
            elif u and not seen[w].get("underlying"):
                seen[w]["underlying"] = u  # 之前名冊對不到標的 → 補標的，出現日不改
        done.add(d)
    doc = {"meta": {"rule": "首批快照已存在的權證 first_seen=null（不算新發行）；缺快照日上市的權證在下一個有快照日才出現，照實記；"
                            "上市以掛牌名冊 basic_twse 為準（PREREG 修訂 R1），名冊標的名稱對不到代號者標的記 null（不計入）、筆數記 unmapped_by_date，日後對到才補標的、出現日不改",
                    "rule_version": RULE_VERSION},
           "dates_processed": sorted(done), "unmapped_by_date": dict(sorted(unmapped_by.items())), "warrants": seen}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return doc


def start_date(px: C.Px, snap: Path = SNAP) -> tuple[str | None, dict]:
    """起跑前提：GATE_DEADLINE 前（含）連續 STREAK_NEED 個交易日快照成功 → START；否則順延到首次達成後下一個月初。
    回傳 (起跑日或 None＝尚未達成, 說明)。"""
    streak, achieved = 0, None
    for d in px.calendar:
        if d < "2026-10-14":
            continue
        streak = streak + 1 if snapshot_ok(d, snap) else 0
        if streak >= STREAK_NEED:
            achieved = d
            break
    info = {"snapshot_streak_need": STREAK_NEED, "streak_achieved_on": achieved, "gate_deadline": GATE_DEADLINE}
    if achieved is None:
        return None, {**info, "start_deferred": None, "why": "權證快照尚未連續 10 個交易日成功"}
    if achieved <= GATE_DEADLINE:
        return START, {**info, "start_deferred": False}
    y, m = int(achieved[:4]), int(achieved[5:7]) + 1
    if m > 12:
        y, m = y + 1, 1
    return f"{y}-{m:02d}-01", {**info, "start_deferred": True}


def signal(ctx: dict, day: str, uni: dict):
    px: C.Px = ctx["px"]
    win = [d for d in px.calendar if d <= day][-W:]
    missing = [d for d in win if not snapshot_ok(d, ctx.get("snap", SNAP))]
    if len(missing) > MAX_MISSING:
        ctx["skip_reason"] = f"近 {W} 個交易日缺快照 {len(missing)} 天（>{MAX_MISSING}），本月不調倉"
        return None
    lo = win[0]
    cnt = {}
    for w in (ctx["appear"].get("warrants") or {}).values():
        fs = w.get("first_seen")
        if fs and lo <= fs <= day and w.get("underlying"):
            cnt[w["underlying"]] = cnt.get(w["underlying"], 0) + 1
    rows = [{"code": c, "new_calls": n, "turnover_20d": round(uni[c] or 0)} for c, n in cnt.items() if c in uni and n >= 1]
    rows.sort(key=lambda r: (-r["new_calls"], r["turnover_20d"], r["code"]))
    return rows


def spec() -> C.Spec:
    return C.Spec(key="paper_12", label="模擬 L 認購權證發行潮",
                  note="每月第一個交易日：近 20 個交易日新發行認購權證檔數排名前 20 進場、跌出前 60 出場、等權；近 20 日均成交值 ≥3,000 萬；成本 1×",
                  prereg=PREREG, trial_no=TRIAL_NO, start_not_before=START, judge_after=JUDGE, mode="monthly",
                  top_n=M, exit_rank=R, min_turnover=MIN_TURNOVER, delist_value="last", signal=signal,
                  log_path=ROOT / "research" / "data" / "paper_12_log.jsonl", out_path=ROOT / "data" / "paper_12.json",
                  judge_text=("2028-12-01 後判一次（起跑順延也不延後）：已平倉 ≥100 筆前提；天條一回撤 ≤50%；扣 1× 年化 > 0050 含息；"
                              "2×／3× 成本年化 >0；隨機時點對照 > 第 95 百分位（1,000 次、seed 20261201）"),
                  known_limit="快照只在本機、曾多次缺日（單點依賴）；檔數不等於避險部位大小")


def step() -> dict:
    px = C.load_px()
    appear = update_appearances()
    start, info = start_date(px)
    ctx = {"px": px, "appear": appear, "summary_extra": info}
    if start is None:
        sp = spec()
        C.write_summary(sp, px, C.read_log(sp), {"why_not_started": info["why"], **info})
        return {"state": "NOT_STARTED", "gate": info}
    return {**C.step(spec(), ctx, px=px, start_override=start), "gate": info}


if __name__ == "__main__":
    raise SystemExit(C.run_main(step, "模擬 L", ROOT / "data" / "paper_12.json"))
