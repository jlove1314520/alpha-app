# -*- coding: utf-8 -*-
"""先.一三〇-3／收件匣 019 A4（2026-10-23）：減資還原 unresolved 缺口補齊（零請求、不算任何 V1 報酬）。

var1018_v1_reduction_events.py 推導不出參考價的停牌缺口（找不到停牌前／恢復日收盤 125 件、上市恢復日漲跌欄「X 不比價」51 件）：
1. 先用本機 FinMind 原始收盤快取（V1 抓的 2006-01-01～2014-12-31）補停牌前收盤（≤ from 的最後一天）與恢復日收盤（≥ to 的第一天），
   沒有 FinMind 再用官方日檔快取（data/v1_official_daily/）；
2. 仍推導不出參考價者，依 Cowork 019 審查④：**跨停牌那一段報酬設 0（視為純減資換算）**＝係數＝恢復日收盤 ÷ 停牌前收盤，
   kind＝reduction_assumed、source＝assumed_zero_return_across_halt（與官方／推導的 reduction 分開標，結果要揭露件數與名單）；
   |係數−1| < 0.5% 記 pure_halt（不調整）；
3. 前後收盤跳動 >±20% 的全部列表（含官方／推導已解決的）；兩種收盤都找不到的列為「完全無法解析」。
輸出：覆寫 data/v1_reduction_events_2007_2014.csv（先備份成 *.before_fill_20261023.csv）、data/v1_reduction_fill_report.json。
跑法：cd research && python var1018_v1_reduction_fill_unresolved.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import pandas as pd

import finmind_client as F
import var1018_v1_halt_check as H
import var1018_v1_prep as V

D = Path(__file__).parent / "data"
EV = D / "v1_reduction_events_2007_2014.csv"
REP = D / "v1_reduction_events_report.json"
OFF = D / "v1_official_daily"
OUT_REP = D / "v1_reduction_fill_report.json"
PURE = 0.005
JUMP = 0.20


def finmind_closes(code: str) -> pd.Series:
    if not V.cached("TaiwanStockPrice", code):
        return pd.Series(dtype=float)
    d = F.load_dev("TaiwanStockPrice", code, V.FETCH_START, V.FETCH_END)
    if d.empty:
        return pd.Series(dtype=float)
    s = pd.Series(pd.to_numeric(d["close"], errors="coerce").to_numpy(), index=d["date"].astype(str).str[:10])
    return s[s > 0].sort_index()


def official_close(code: str, ymd: str) -> float | None:
    for src in ("twse", "tpex"):
        p = OFF / src / f"{ymd.replace('-', '')}.json"
        if p.exists():
            r = (json.loads(p.read_text(encoding="utf-8")).get("rows") or {}).get(code)
            if r and r[3]:
                return float(r[3])
    return None


def main() -> int:
    rep = json.loads(REP.read_text(encoding="utf-8"))
    ev = pd.read_csv(EV, dtype={"stock_id": str})
    bak = EV.with_name(EV.stem + ".before_fill_20261023.csv")
    if not bak.exists():
        shutil.copyfile(EV, bak)
    have = {(r.stock_id, r.halt_from, r.halt_to) for r in ev.itertuples()}
    add, impossible = [], []
    for u in rep["unresolved"]:
        code, a, b = u["code"], u["from"], u["to"]
        if (code, a, b) in have:
            continue
        s = finmind_closes(code)
        pre_d = s.index[s.index <= a].max() if (s.index <= a).any() else None
        post_d = s.index[s.index >= b].min() if (s.index >= b).any() else None
        pc = float(s[pre_d]) if pre_d else (u.get("pre_close") or official_close(code, a))
        rc = float(s[post_d]) if post_d else (u.get("resume_close") or official_close(code, b))
        pre_d, post_d = pre_d or a, post_d or b
        if not (pc and rc):
            impossible.append({"code": code, "from": a, "to": b, "why": "FinMind 與官方快取都找不到停牌前／恢復日收盤"})
            continue
        f = rc / pc
        add.append({"stock_id": code, "market": "", "halt_from": a, "halt_to": b, "pre_date": pre_d, "pre_close": pc,
                    "resume_date": post_d, "resume_close": rc, "ref_price": rc, "factor": round(f, 6),
                    "source": "assumed_zero_return_across_halt",
                    "kind": "pure_halt" if abs(f - 1) < PURE else "reduction_assumed"})
    # 2. 掃全部候選：halt_check 只列「讓該股未涵蓋」的缺口，涵蓋股裡的減資停牌（例 1526 2010-09-30→10-20，13 個交易日、
    #    6.91→8.13，FinMind 減資表也沒有）不在清單。原始收盤相鄰兩筆隔 ≥5 個營業日、且跳動 >±10%（2015-06 前漲跌幅 ±7%，
    #    除息是連續交易日、不會被「隔 ≥5 天」選到）→ 視為未入帳的減資停牌，同樣用「跨停牌報酬設 0」，與既有事件同股 ±7 天內不重複。
    known = pd.concat([ev, pd.DataFrame(add)], ignore_index=True) if add else ev
    known_dates = {}
    for r in known.itertuples():
        known_dates.setdefault(r.stock_id, []).append(pd.Timestamp(r.resume_date))
    cands, _dead = V.candidates()
    # 交易日曆：當天 ≥200 檔候選有收盤＝市場有開（不能用平日：農曆年等連假一週，跨年假的正常漲跌會被誤判）
    from collections import Counter
    cnt = Counter()
    for code in cands:
        cnt.update(finmind_closes(code).index)
    cal = sorted(d for d, n in cnt.items() if n >= 200)
    cal_pos = {d: i for i, d in enumerate(cal)}
    scanned = 0
    suspects: list = []
    halt_cache: dict = {}
    for code in cands:
        s = finmind_closes(code)
        if len(s) < 2:
            continue
        scanned += 1
        idx = pd.to_datetime(s.index)
        for i in range(1, len(s)):
            a_, b_ = cal_pos.get(s.index[i - 1]), cal_pos.get(s.index[i])
            gap_bd = (b_ - a_ - 1) if a_ is not None and b_ is not None else 0  # 中間「市場有開、這檔沒價格」的交易日數
            j = s.iloc[i] / s.iloc[i - 1] - 1
            if gap_bd < 5 or abs(j) <= 0.10:
                continue
            if any(abs(idx[i] - k) <= pd.Timedelta(days=7) for k in known_dates.get(code, [])):
                continue
            # 只收「官方確認停牌」（中間每個營業日全市場官方日檔都有、這檔沒列）：真的沒交易，跳動只能來自參考價變動；
            # 其餘（多為 2007 上半年 FinMind 缺列、上櫃官方檔 2007-07 才有）可能是照常交易但資料缺，跳動是真報酬 → 只列清單不補。
            cls = H.classify_interval(code, idx[i - 1], idx[i], halt_cache)
            if cls != "official_absent":
                suspects.append({"stock_id": code, "pre_date": s.index[i - 1], "resume_date": s.index[i],
                                 "pre_close": float(s.iloc[i - 1]), "resume_close": float(s.iloc[i]),
                                 "jump": round(float(j), 4), "trading_days_missing": int(gap_bd), "class": cls})
                continue
            f = s.iloc[i] / s.iloc[i - 1]
            add.append({"stock_id": code, "market": "", "halt_from": s.index[i - 1], "halt_to": s.index[i],
                        "pre_date": s.index[i - 1], "pre_close": float(s.iloc[i - 1]), "resume_date": s.index[i],
                        "resume_close": float(s.iloc[i]), "ref_price": float(s.iloc[i]), "factor": round(f, 6),
                        "source": "assumed_zero_return_official_halt_scan", "kind": "reduction_assumed"})
            known_dates.setdefault(code, []).append(idx[i])
    print(f"全候選掃描 {scanned} 檔，另補 {sum(1 for r in add if r['source'] == 'assumed_zero_return_official_halt_scan')} 件（官方確認停牌）；疑似但未確認、只列清單 {len(suspects)} 件", flush=True)
    out = pd.concat([ev, pd.DataFrame(add)], ignore_index=True).sort_values(["stock_id", "resume_date"])
    out.to_csv(EV, index=False)
    jumps = out[(out["resume_close"] / out["pre_close"] - 1).abs() > JUMP]
    res = {"generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
           "n_before": len(ev), "n_added": len(add), "n_total": len(out),
           "by_kind": out["kind"].value_counts().to_dict(), "by_source": out["source"].value_counts().to_dict(),
           "n_impossible": len(impossible), "impossible": impossible,
           "assumed_zero_return_list": [{k: r[k] for k in ("stock_id", "pre_date", "resume_date", "pre_close", "resume_close", "factor")}
                                        for r in add if r["kind"] == "reduction_assumed"],
           "gap_scan_suspects_not_added": suspects, "n_gap_scan_suspects_not_added": len(suspects),
           "jumps_over_20pct": jumps[["stock_id", "pre_date", "resume_date", "pre_close", "resume_close", "factor", "source", "kind"]]
           .to_dict("records")}
    OUT_REP.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k not in ("impossible", "assumed_zero_return_list", "jumps_over_20pct", "gap_scan_suspects_not_added")},
                     ensure_ascii=False), flush=True)
    print(f"跳動 >±20%：{len(jumps)} 件；完全無法解析：{len(impossible)} 件", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
