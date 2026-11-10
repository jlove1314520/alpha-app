# -*- coding: utf-8 -*-
"""先.一五六-1b 台股擂台跟單紙上帳（往後逐週）——研究帽產物，零外部請求（不對 udn 送任何請求）。

輸入：research/data/arena_picks.jsonl（Cowork 每週日依搜尋結果寫入；每行一位分析師一週：week_of／analyst／persona／picks[{name,code}]／source_url）。
價格：data/price_history（每日排程；還原開盤＝開盤×還原收盤÷收盤）。

四個版本（每週第一個交易日開盤換股、持有到下一個有名單的週的第一個交易日開盤）：
  A 全跟：當週所有分析師的所有選股等權（同一檔被多人選只算一次）。
  B 共識：≥2 位分析師同選的才買（等權）；沒有就持 0050。
  C 跟上週贏家：上一週（開盤到下週開盤）等權報酬最高的那位分析師，本週照他的選股等權；
     〔自行裁量〕第一週沒有上一週可比 → 同 A。
  D 全跟 2×：A 的日報酬 ×2，多出的 1 倍付融資 6.5%/年。
成本：換股時照目標權重與漂移後權重差，買方 手續費 0.1425%＋滑價 5bps，賣方再加證交稅（00 開頭 ETF 0.1%、其餘 0.3%），validation.costs 1×。
〔自行裁量〕某週沒有新名單（Cowork 沒更新）→ 續抱上一週持股，不換股；某檔當天沒價格（停牌）→ 當天 0 報酬、仍算在權重裡。
〔自行裁量〕week_of＝該週週一；假設名單在週一開盤前已公開（台股擂台每週刊出），若之後查到刊出時間晚於週一開盤，入場要改成刊出後下一個開盤。
signal_ledger 舊的擂台線索（2492 華新科，楊育華 10/21「台股擂台／股市御錢術」，signal_ledger id f7ebf322e1333c06，
  t5 −3.26%）在起跑日 11/09 之前、不倒填進紙上帳，只記在 state_arena.json 的 history_note 供對照。

輸出（append-only）：research/data/paper_opt/ledger_ARENA_{A,B,C,D}.jsonl、state_arena.json
用法：python research/paper_opt_arena.py
非投資建議。
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
import paper_opt_f12 as F12  # noqa: E402
from validation import costs as costmod  # noqa: E402  （只呼叫、不改）

OUT = F12.OUT
PICKS = HERE / "data" / "arena_picks.jsonl"
STATE = OUT / "state_arena.json"
START = "2026-11-09"
VERSIONS = ("A", "B", "C", "D")
SLIP = 5.0 / 10_000
BUY = costmod.COMMISSION_RATE + SLIP
MARGIN_RATE = 0.065 / 252.0
MIN_TRADED = 1000
HISTORY_NOTE = {"signal_ledger_id": "f7ebf322e1333c06", "code": "2492", "name": "華新科", "analyst": "楊育華（股市御錢術）",
                "event_date": "2026-10-21", "entry_date": "2026-10-22", "t5_return_pct": -3.2609,
                "note": "起跑日前的單筆擂台線索，不倒填進紙上帳，只供對照"}


def sell_rate(code: str) -> float:
    return costmod.COMMISSION_RATE + SLIP + costmod.tax_rate("etf" if code.startswith("00") else "normal")


def load_picks() -> dict[str, list[dict]]:
    weeks: dict[str, list[dict]] = {}
    if not PICKS.exists():
        return weeks
    for ln in PICKS.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            r = json.loads(ln)
            weeks.setdefault(r["week_of"], []).append(r)
    return weeks


def load_prices(codes: set[str]) -> tuple[dict, list[str]]:
    """{代號: {日期: (還原開盤, 還原收盤)}}、完整交易日曆。"""
    px: dict = {}
    cnt: dict[str, int] = {}
    for f in sorted(glob.glob(str(REPO / "data" / "price_history" / "b*.json"))):
        try:
            prices = json.loads(Path(f).read_text(encoding="utf-8"))["prices"]
        except Exception as e:  # 單一分片壞掉只略過
            print(f"[warn] 讀不到 {f}：{e}")
            continue
        for sid, rows in prices.items():
            for r in rows:
                if (r.get("close") or 0) > 0 and r.get("date", "") >= "2026-10-01":
                    cnt[r["date"]] = cnt.get(r["date"], 0) + 1
            if sid in codes:
                for r in rows:
                    c, a, o = r.get("close") or 0, r.get("adj_close") or 0, r.get("open") or 0
                    if c > 0 and a > 0 and o > 0:
                        px.setdefault(sid, {})[r["date"]] = (o * a / c, a)
    cal = sorted(d for d, n in cnt.items() if n >= MIN_TRADED)
    return px, cal


def eq_weights(codes: list[str]) -> dict[str, float]:
    u = list(dict.fromkeys(codes))
    return {c: 1.0 / len(u) for c in u} if u else {}


def targets(week: list[dict], prev_winner: str | None) -> dict[str, dict[str, float]]:
    allc = [p["code"] for r in week for p in r["picks"]]
    cnt: dict[str, int] = {}
    for r in week:
        for c in {p["code"] for p in r["picks"]}:
            cnt[c] = cnt.get(c, 0) + 1
    cons = [c for c in dict.fromkeys(allc) if cnt[c] >= 2]
    win = next((r for r in week if r["analyst"] == prev_winner), None)
    a = eq_weights(allc)
    return {"A": a, "B": eq_weights(cons) if cons else {"0050": 1.0},
            "C": eq_weights([p["code"] for p in win["picks"]]) if win else a, "D": a}


def main() -> int:
    weeks = load_picks()
    if not weeks:
        print("[warn] arena_picks.jsonl 沒有資料，不記帳")
        return 0
    codes = {p["code"] for ws in weeks.values() for r in ws for p in r["picks"]} | {"0050"}
    px, cal = load_prices(codes)
    st = F12._rj(STATE, None) or {"start": START, "last_date": None, "applied_week": None, "history_note": HISTORY_NOTE,
                                    "v": {k: {"w": {}, "account": 1.0} for k in VERSIONS},
                                    "analyst_week": {}, "prev_winner": None}
    done = 0
    for i, d in enumerate(cal):
        if d < st["start"] or (st["last_date"] and d <= st["last_date"]):
            continue
        prev = cal[i - 1] if i > 0 else None
        wk = max((w for w in weeks if w <= d), default=None)
        rebal = wk is not None and wk != st["applied_week"]
        # 換股前先結算上一週各分析師（開盤到開盤）報酬 → 決定 C 版贏家
        if rebal and st["applied_week"]:
            aw = st["analyst_week"].get(st["applied_week"], {})
            perf = {}
            for an, info in aw.items():
                rs = [px[c][d][0] / info["entry"][c] - 1.0 for c in info["entry"] if c in px and d in px[c]]
                if rs:
                    perf[an] = sum(rs) / len(rs)
            if perf:
                st["prev_winner"] = max(perf, key=perf.get)
                st.setdefault("analyst_perf", {})[st["applied_week"]] = {k: round(v, 6) for k, v in perf.items()}
        tg = targets(weeks[wk], st["prev_winner"]) if rebal else None
        recs = {}
        for k in VERSIONS:
            v = st["v"][k]
            w = v["w"]
            r_on = 0.0
            cost = 0.0
            if rebal:
                # 隔夜（前收→今開）先算在舊持股上
                for c, wt in w.items():
                    if c in px and d in px[c] and prev in px[c]:
                        r_on += wt * (px[c][d][0] / px[c][prev][1] - 1.0)
                tot = sum(w.values())
                cash = 1.0 - tot
                g = {c: wt * ((px[c][d][0] / px[c][prev][1]) if c in px and d in px[c] and prev in px[c] else 1.0) for c, wt in w.items()}
                gs = sum(g.values()) + cash
                drift = {c: x / gs for c, x in g.items()} if gs > 0 else {}
                new = tg[k]
                for c in set(drift) | set(new):
                    dw = new.get(c, 0.0) - drift.get(c, 0.0)
                    cost += dw * BUY if dw > 0 else -dw * sell_rate(c)
                r_in = sum(wt * ((px[c][d][1] / px[c][d][0] - 1.0) if c in px and d in px[c] else 0.0) for c, wt in new.items())
                r1 = (1.0 + r_on) * (1.0 - cost) * (1.0 + r_in) - 1.0
                w = dict(new)
            else:
                r1 = sum(wt * ((px[c][d][1] / px[c][prev][1] - 1.0) if c in px and d in px[c] and prev in px[c] else 0.0)
                         for c, wt in w.items())
            # 權重漂移
            gr = {c: wt * (1.0 + (((px[c][d][1] / (px[c][d][0] if rebal else px[c][prev][1])) - 1.0)
                                  if c in px and d in px[c] and (rebal or prev in px[c]) else 0.0)) for c, wt in w.items()}
            cash = 1.0 - sum(w.values())
            gs = sum(gr.values()) + cash
            v["w"] = {c: x / gs for c, x in gr.items()} if gs > 0 else {}
            r = 2.0 * r1 - MARGIN_RATE if k == "D" else r1
            v["account"] = max(v["account"] * (1.0 + r), 0.0)
            recs[k] = {"date": d, "ret": round(r, 8), "ret_1x": round(r1, 8), "account": round(v["account"], 8),
                       "week_of": wk, "rebalance": rebal, "cost": round(cost, 6),
                       "holdings": {c: round(x, 4) for c, x in v["w"].items()},
                       "missing_price": [c for c in v["w"] if c not in px or d not in px[c]]}
        if rebal:
            st["analyst_week"][wk] = {r["analyst"]: {"entry": {p["code"]: px[p["code"]][d][0] for p in r["picks"]
                                                              if p["code"] in px and d in px[p["code"]]}} for r in weeks[wk]}
            st["applied_week"] = wk
            recs["C"]["follow"] = st["prev_winner"] or "第一週無上週可比→同 A"
        for k in VERSIONS:
            with (OUT / f"ledger_ARENA_{k}.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(recs[k], ensure_ascii=False) + "\n")
        st["last_date"] = d
        done += 1
        print(f"{d} " + "　".join(f"{k} {recs[k]['ret']:+.2%}" for k in VERSIONS) + ("（換股）" if rebal else ""))
    F12._wj(STATE, st)
    print(f"本次寫入 {done} 個交易日（起跑 {st['start']}，最後 {st['last_date']}）")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 十二節：自身失敗只印警告、exit 0
        import traceback
        traceback.print_exc()
        print(f"[warn] paper_opt_arena 失敗：{e}")
        sys.exit(0)
