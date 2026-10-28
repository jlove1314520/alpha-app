# -*- coding: utf-8 -*-
"""模擬 J：處置股解除後反彈（只做多、處置期間下跌者）前向紙上追蹤（先.一三二-5，試驗 #見 PREREG）。

規則照 `docs/PREREG_DISPOSITION_RELEASE_REBOUND_FORWARD_FINAL.md` §F1（H=20、M=20，一次定死）；共用部分在
research/paper_forward_common.py，本檔只有：處置事件累積、訊號函式、條件有效性對照（影子帳本）。
- 事件來源 data/disposal_flags.json（本機 AlphaDisposalFlags 每日 18:30 產生並 commit），每次執行併進
  research/data/paper_10_events.json（12/01 前也照常累積，只累積、不建倉），零額外外部請求。
- `limit_up_at_entry`（PREREG 修訂 R1，先.一四一-1）：r+1 原始收盤 ≥ r+1 官方漲停價（research/official_limit.py：
  上櫃用前一日 TPEx 公告次日漲停價、缺檔或上市用 tw_limit_price 計算；除權息日基準用參考價），來源記 limit_src／limit_base。
- 主帳本 research/data/paper_10_log.jsonl＋摘要 data/paper_10.json；影子帳本（處置期間報酬 ≥0）
  research/data/paper_10_control_log.jsonl＋research/data/paper_10_control.json。
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import paper_forward_common as C
from official_limit import OfficialLimits

ROOT = C.ROOT
EVENTS = ROOT / "research" / "data" / "paper_10_events.json"
FLAGS = ROOT / "data" / "disposal_flags.json"
H, M = 20, 20
MIN_PRE_TURNOVER = 10_000_000.0
START = "2026-12-01"
JUDGE = "2028-12-01"
PREREG = "docs/PREREG_DISPOSITION_RELEASE_REBOUND_FORWARD_FINAL.md"
TRIAL_NO = 464  # register_trial() 2026-10-23


def accumulate(flags_path: Path = FLAGS, events_path: Path = EVENTS, today: str | None = None) -> dict:
    """把當下的處置紀錄併進累積檔（以（代號、起日）去重；已存在的只更新迄日——延長公告可能改迄日）。"""
    doc = C.load_json(events_path, {}) or {}
    segs = {(s["code"], s["start"]): s for s in doc.get("segments") or []}
    flags = C.load_json(flags_path, {}) or {}
    seen = today or datetime.now(C.TW).date().isoformat()
    for code, r in (flags.get("disposal") or {}).items():
        if not r or not r.get("start") or not r.get("end"):
            continue
        k = (str(code), r["start"])
        if k in segs:
            segs[k]["end"] = max(segs[k]["end"], r["end"])
            segs[k]["last_seen"] = seen
        else:
            segs[k] = {"code": str(code), "start": r["start"], "end": r["end"], "announced": r.get("announced"),
                       "source": r.get("source"), "first_seen": seen, "last_seen": seen}
    out = {"meta": {"source": "data/disposal_flags.json（Shioaji punish 為主、TWSE／TPEx openapi 備援）",
                    "updated_at": datetime.now(C.TW).isoformat(timespec="seconds"), "n_segments": len(segs)},
           "segments": sorted(segs.values(), key=lambda s: (s["code"], s["start"]))}
    events_path.parent.mkdir(parents=True, exist_ok=True)
    events_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def merged_events(segments: list, px: C.Px) -> list:
    """同代號處置期間重疊或首尾相接（下一段起日 ≤ 上一段迄日的下一個交易日）→ 合併成一個事件。"""
    by = {}
    for s in segments:
        by.setdefault(s["code"], []).append(s)
    out = []
    for code, ss in by.items():
        ss = sorted(ss, key=lambda s: s["start"])
        cur = dict(ss[0])
        for s in ss[1:]:
            nxt = px.next_trading_day(cur["end"])
            if nxt is None:  # 價格日曆還沒到：退回日曆天 ≤4 天視為相接
                nxt_ok = (date.fromisoformat(s["start"]) - date.fromisoformat(cur["end"])).days <= 4
            else:
                nxt_ok = s["start"] <= nxt
            if nxt_ok:
                cur["end"] = max(cur["end"], s["end"])
            else:
                out.append(cur)
                cur = dict(s)
        out.append(cur)
    return out


def make_signal(segments: list, control: bool):
    def signal(ctx: dict, day: str, uni: dict) -> list:
        px: C.Px = ctx["px"]
        r = px.prev_trading_day(day)
        cands, skips = [], []
        for ev in merged_events(segments, px):
            if ev["end"] != r:
                continue
            code = ev["code"]
            if any(s["code"] == code and s["start"] <= day <= s["end"] for s in segments):
                continue  # 仍在處置中（延長／再處置）＝未解除
            if code not in uni:
                skips.append({"code": code, "reason": "不在宇宙（非普通股／不在市／當天無收盤）"})
                continue
            s0 = px.prev_trading_day(ev["start"])
            p0, p1 = (px.close_on(code, s0) if s0 else None), px.close_on(code, r)
            if not p0 or not p1:
                skips.append({"code": code, "reason": "處置起日前一日或解除日缺收盤"})
                continue
            liq = px.avg_turnover(code, ev["start"], inclusive=False)
            if liq is None or liq < MIN_PRE_TURNOVER:
                skips.append({"code": code, "reason": "處置前 20 日均成交值不足 1,000 萬或資料不滿 20 天"})
                continue
            ret = p1 / p0 - 1
            if (ret >= 0) != control:
                continue
            raw_r, raw_d = px.raw_close_on(code, r), px.raw_close_on(code, day)
            lim = ctx.get("limits") or ctx.setdefault("limits", OfficialLimits())
            lp = lim.limits(code, day, r, raw_r)
            cands.append({"code": code, "disposal_start": ev["start"], "release_date": r, "disposal_ret": round(ret, 6),
                          "pre_turnover_20d": round(liq),
                          "limit_up_at_entry": bool(lp and raw_d and raw_d >= lp["up"] - 1e-9),
                          "limit_up_price": lp["up"] if lp else None, "limit_src": lp["src"] if lp else "unavailable",
                          "limit_base": lp["base_src"] if lp else None})
        cands.sort(key=lambda c: (c["disposal_ret"], c["code"]))
        ctx.setdefault("skips", {})[day] = skips
        return cands
    return signal


def specs(segments: list) -> tuple[C.Spec, C.Spec]:
    judge = ("2028-12-01 後判一次：已平倉 ≥100 筆前提；天條一回撤 ≤50%；扣 1× 年化 > 0050 含息；2×／3× 成本年化 >0；"
             "隨機時點對照 > 第 95 百分位（1,000 次、seed 20261201）；影子帳本（處置期間上漲者）最終淨值須低於本線")
    base = dict(start_not_before=START, judge_after=JUDGE, mode="event", top_n=M, hold_days=H, delist_value="zero",
                prereg=PREREG, trial_no=TRIAL_NO, judge_text=judge,
                known_limit="前向 24 個月，處置事件年均約 300 件、條件後約一半；檢定力有限")
    main = C.Spec(key="paper_10", label="模擬 J 處置股解除後反彈",
                  note="處置期間下跌的股票，在處置解除後隔天收盤買進、持有 20 個交易日；最多 20 檔、每筆淨值 1/20；成本 1×",
                  signal=make_signal(segments, control=False), log_path=ROOT / "research" / "data" / "paper_10_log.jsonl",
                  out_path=ROOT / "data" / "paper_10.json", **base)
    ctrl = C.Spec(key="paper_10_control", label="模擬 J 影子帳本（處置期間上漲者，條件有效性對照）",
                  note="同規則、改挑處置期間報酬 ≥0 的事件；只作判準⑤對照，不是候選",
                  signal=make_signal(segments, control=True), log_path=ROOT / "research" / "data" / "paper_10_control_log.jsonl",
                  out_path=ROOT / "research" / "data" / "paper_10_control.json", **base)
    return main, ctrl


def step() -> dict:
    doc = accumulate()
    px = C.load_px()
    main, ctrl = specs(doc["segments"])
    ctx = {"px": px, "summary_extra": {"events_accumulated": len(doc["segments"])}}
    a = C.step(main, ctx, px=px)
    b = C.step(ctrl, {"px": px}, px=px)
    return {"main": a, "control": b, "segments": len(doc["segments"])}


if __name__ == "__main__":
    raise SystemExit(C.run_main(step, "模擬 J", ROOT / "data" / "paper_10.json"))
