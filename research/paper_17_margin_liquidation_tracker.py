# -*- coding: utf-8 -*-
"""模擬 Q：融資餘額驟減＋大跌（疑似斷頭賣壓）後反彈 前向紙上追蹤（先.一三六-B7）。

規則照 `docs/PREREG_MARGIN_LIQUIDATION_REBOUND_FORWARD_FINAL.md`（§5-1 甲；D＝10%、R＝5%、H＝5、M＝20，一次定死）；
共用部分在 research/paper_forward_common.py，本檔只有訊號函式。
- 事件 t0：前一交易日融資餘額 ≥500 張、t0 餘額 ÷ 前一日 −1 ≤ −D、t0 官方收盤報酬 ≤ −R、t0 不是除權息日。
- t1（t0 下一個交易日）收盤買進；t1 漲停鎖死 → 放棄、不遞延；同代號 20 個交易日內只算第一個事件；
  t0 前 20 個交易日均成交值 ≥1,000 萬；同日超額依代號排序；下市無後續價格以 −100% 計。
- 揭露欄（不判定）：同日事件檔數、t0 是否同時有重大訊息（mops_events_archive）；t0 加權指數報酬 price_history 沒有指數序列，記 null。
- ⚠️ data/margin_by_stock_history.json 的日期鍵是「管線執行日」不是資料日（先.一三五-1e 發現）。先.一三六-B7a（2026-10-28）起
  累積檔另存 `data_dates`（執行日鍵 → 上市／上櫃官方資料日）：**有資料日就用資料日當 t0**（同一資料日只算第一次）；
  沒有的舊鍵才退回後備＝去掉與前一鍵相同的複本、把鍵對到 ≤ 該鍵的最後交易日（[自行裁量]，某班在資料更新前執行時事件日可能晚一個交易日）。
資料：data/margin_by_stock_history.json（每日管線既有呼叫累積）＋data/price_history＋data/ex_dividend_events.json，零額外外部請求。
"""
from __future__ import annotations

import json

import paper_forward_common as C
import paper_forward_events as E

ROOT = C.ROOT
D_DROP, R_DROP, H, M = 0.10, 0.05, 5, 20
MIN_PREV_BAL = 500.0          # 張
MIN_PRE_TURNOVER = 10_000_000.0
DEDUPE_DAYS = 20
START = "2027-01-04"
JUDGE = "2029-01-02"
PREREG = "docs/PREREG_MARGIN_LIQUIDATION_REBOUND_FORWARD_FINAL.md"
TRIAL_NO = 488  # register_trial() #488（2026-10-27 互動視窗 先.一三七-1 登記）
MARGIN = ROOT / "data" / "margin_by_stock_history.json"
EXDIV = ROOT / "data" / "ex_dividend_events.json"
NEWS = ROOT / "research" / "data" / "mops_events_archive.jsonl"


def ex_dates(doc: dict) -> dict:
    return {c: {e.get("ex_date") for e in evs or [] if e.get("ex_date")} for c, evs in ((doc or {}).get("events") or {}).items()}


def data_day(margin: dict, d8: str, code: str) -> str | None:
    """先.一三六-B7a：執行日鍵 d8 對應的官方資料日（ISO）；累積檔沒記就回 None（走後備）。"""
    dd = ((margin or {}).get("data_dates") or {}).get(d8) or {}
    tp = (margin or {}).get("tpex_codes") or ()
    mkt = "tpex" if code in (tp if isinstance(tp, set) else set(tp)) else "twse"
    v = dd.get(mkt)
    return E.iso(v) if v else None


def resolve_t0(px: C.Px, margin: dict, d8: str, code: str) -> str | None:
    """t0：有資料日且是交易日 → 資料日；資料日不在價格日曆（休市或價格還沒進來）→ None；沒資料日 → 後備 ≤ 鍵的最後交易日。"""
    dday = data_day(margin, d8, code)
    if dday:
        i = E.tindex(px, dday)
        return dday if i >= 0 and px.calendar[i] == dday else None
    i = E.tindex(px, E.iso(d8))  # 後備：週六／休市日的鍵 → 對到 ≤ 該鍵的最後交易日（[自行裁量]，見檔頭）
    return px.calendar[i] if i >= 0 else None


def raw_events(margin: dict, px: C.Px, exd: dict) -> list:
    out = []
    tpex = set((margin or {}).get("tpex_codes") or [])
    margin = {**(margin or {}), "tpex_codes": tpex}
    for code, ser in ((margin or {}).get("series") or {}).items():
        if not C.is_common(code):
            continue
        last_v, seen_days = None, set()
        for d8, v in sorted((ser or {}).items()):
            if not v or len(v) < 2 or v[0] is None or v[1] is None:
                continue
            dday = data_day(margin, d8, code)
            if dday:
                if dday in seen_days:
                    continue  # 同一官方資料日（執行日不同）只算第一次；新舊鍵對到同一事件由 E.dedupe（同代號 20 日）去掉
                seen_days.add(dday)
            elif last_v is not None and list(v) == list(last_v):
                continue  # 後備：沒資料日的舊鍵，TWSE／TPEx 未更新時是前一鍵的原樣複本（先.一三五-1e 發現），去掉
            last_v = v
            t0 = resolve_t0(px, margin, d8, code)
            if t0 is None:
                continue
            today, prev = float(v[0]), float(v[1])
            if prev < MIN_PREV_BAL or today / prev - 1 > -D_DROP:
                continue
            if t0 in exd.get(code, set()):
                continue
            r = E.raw_ret(px, code, t0)
            if r is None or r > -R_DROP:
                continue
            out.append({"code": code, "t0": t0, "margin_chg": round(today / prev - 1, 6), "t0_ret": round(r, 6)})
    return E.dedupe(out, px, DEDUPE_DAYS)


def news_by_day() -> set:
    keys = set()
    try:
        for l in NEWS.read_text(encoding="utf-8").splitlines():
            if l.strip():
                e = json.loads(l)
                keys.add((str(e.get("code")), e.get("date")))
    except (OSError, ValueError):
        pass
    return keys


def make_signal(events: list, news: set):
    by_t0 = {}
    for ev in events:
        by_t0.setdefault(ev["t0"], []).append(ev)

    def signal(ctx: dict, day: str, uni: dict) -> list:
        px: C.Px = ctx["px"]
        t0 = px.prev_trading_day(day)
        todays = by_t0.get(t0) or []
        cands, skips = [], []
        for ev in todays:
            code = ev["code"]
            if code not in uni:
                skips.append({"code": code, "reason": "不在宇宙（非普通股／不在市／t1 無收盤）"})
                continue
            liq = px.avg_turnover(code, t0, inclusive=False)
            if liq is None or liq < MIN_PRE_TURNOVER:
                skips.append({"code": code, "reason": "t0 前 20 日均成交值不足 1,000 萬或資料不滿 20 天"})
                continue
            if E.locked_up(px, code, day):
                skips.append({"code": code, "reason": "t1 漲停鎖死，放棄不遞延"})
                continue
            cands.append({**ev, "pre_turnover_20d": round(liq), "same_day_events": len(todays),
                          "has_material_news_t0": (code, t0) in news, "taiex_ret_t0": None})
        cands.sort(key=lambda c: c["code"])
        ctx.setdefault("skips", {})[day] = skips
        return cands
    return signal


def spec(events: list, news: set) -> C.Spec:
    return C.Spec(key="paper_17", label="模擬 Q 融資驟減大跌後反彈",
                  note="融資單日減 ≥10%＋當日跌 ≥5% 的隔天收盤買進、持有 5 個交易日；最多 20 檔、每筆淨值 1/20；成本 1×",
                  prereg=PREREG, trial_no=TRIAL_NO, start_not_before=START, judge_after=JUDGE, mode="event",
                  top_n=M, hold_days=H, delist_value="zero", signal=make_signal(events, news),
                  log_path=ROOT / "research" / "data" / "paper_17_log.jsonl", out_path=ROOT / "data" / "paper_17.json",
                  judge_text=("2029-01-02 後判一次：已平倉 ≥100 筆前提；天條一回撤 ≤50%；扣 1× 年化 > 0050 含息；"
                              "2×／3× 成本年化 >0；隨機時點對照 > 第 95 百分位（1,000 次、seed 20270104）"),
                  known_limit="融資減少不全是斷頭（也有主動了結、現償），無法逐筆區分；24 個月若無急跌段事件會集中在個股利空日",
                  extra_summary={"events_source": "data/margin_by_stock_history.json（2026-09-29 起前向累積）"})


def step() -> dict:
    px = C.load_px()
    evs = raw_events(C.load_json(MARGIN, {}), px, ex_dates(C.load_json(EXDIV, {})))
    return C.step(spec(evs, news_by_day()), {"px": px, "summary_extra": {"raw_events_after_dedupe": len(evs)}}, px=px)


if __name__ == "__main__":
    raise SystemExit(C.run_main(step, "模擬 Q", ROOT / "data" / "paper_17.json"))
