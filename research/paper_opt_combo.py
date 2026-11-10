# -*- coding: utf-8 -*-
"""先.一五四-1a ⑦ 紙上優化軌 組合 C25／C20／C15 每日合成——研究帽產物，零外部請求。

合成規則（照 paper_opt_track.combo_curve()＝drawdown_fix_combo.py，這裡不調參）：
  成員＝各家族「原版」紙上日報酬（台幣）：
    F11、F12 → 帳本 ret_orig（原版影子帳戶：不乘崩盤條件；2026-11-10 補上前寫過的日子用 state 的 orig_backfill 重播值）；
    F16 → ret_orig（1.5×／停損 20% 原版）；F14、F15、F17 → ret（帳本本身就是原版）。
  權重＝60 日反波動（只用前一日以前的成員紙上報酬）；紙上未滿 60 日前等權（同回測 fillna(1/n)）。每日再平衡回目標權重。
  組合槓桿 L：r_L ＝ L×r − (L−1)×融資 6.5%/年（同回測）。
  再平衡成本（回測沒算，紙上照實計）：單邊換手＝Σ|目標權重−漂移後權重|÷2，× validation.costs.round_trip_cost_pct()（1×）。
    〔自行裁量〕美股成員也用台股成本（含 0.3% 證交稅，偏保守）；成員內部的再平衡成本已在各自帳本扣過。
  交易日曆〔自行裁量〕：各成員帳本日期聯集；某成員那天沒有列（該市場休市）＝0 報酬。
    只處理到「所有成員帳本最後日期的最小值」為止——美股成員晚一天才有當日列，不能先當 0 寫進帳本。
輸出（append-only）：research/data/paper_opt/ledger_<C25|C20|C15>.jsonl、state_combo.json
用法：python research/paper_opt_combo.py
非投資建議。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np  # noqa: E402
import paper_opt_f12 as F12  # noqa: E402
from paper_opt_track import COMBOS  # noqa: E402
from validation import costs as costmod  # noqa: E402  （只呼叫、不改）

OUT = F12.OUT
STATE = OUT / "state_combo.json"
START = "2026-11-09"
VOL_WIN = 60
MARGIN_RATE = 0.065 / 252.0
RT_COST = costmod.round_trip_cost_pct()
ORIG_FIELD = {"F11": "ret_orig", "F12": "ret_orig", "F16": "ret_orig"}


def member_series(fid: str) -> dict[str, float]:
    lp = OUT / f"ledger_{fid}.jsonl"
    if not lp.exists():
        return {}
    back = (F12._rj(OUT / f"state_{fid}.json", {}) or {}).get("orig_backfill") or {}
    field = ORIG_FIELD.get(fid, "ret")
    out = {}
    for ln in lp.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        r = json.loads(ln)
        v = r.get(field)
        if v is None and field != "ret":
            v = back.get(r["date"])
        if v is None:
            print(f"[warn] {fid} {r['date']} 沒有原版報酬欄，該日視為缺值")
            continue
        out[r["date"]] = float(v)
    return out


def run_combo(cid: str, c: dict, st: dict) -> int:
    members = c["members"]
    ser = {f: member_series(f) for f in members}
    if any(not ser[f] for f in members):
        print(f"[warn] {cid} 有成員還沒有紙上帳本：{[f for f in members if not ser[f]]}，不合成")
        return 0
    cutoff = min(max(ser[f]) for f in members)
    days = sorted({d for f in members for d in ser[f] if START <= d <= cutoff})
    s = st.setdefault(cid, {"last_date": None, "w": None, "account": 1.0})
    led = OUT / f"ledger_{cid}.jsonl"
    done = 0
    hist: list[list[float]] = []
    for d in days:
        R = [ser[f].get(d, 0.0) for f in members]
        if s["last_date"] and d <= s["last_date"]:
            hist.append(R)
            continue
        if len(hist) >= VOL_WIN:
            sd = np.std(np.array(hist[-VOL_WIN:]), axis=0, ddof=1)
            iv = np.where(sd > 0, 1.0 / np.where(sd > 0, sd, 1.0), np.nan)
            tgt = iv / np.nansum(iv) if np.isfinite(iv).all() else np.full(len(members), 1.0 / len(members))
            wmode = "inv_vol_60"
        else:
            tgt = np.full(len(members), 1.0 / len(members))
            wmode = f"equal（紙上 {len(hist)}/{VOL_WIN} 日）"
        prev_w = np.array(s["w"]) if s["w"] else None
        turnover = float(np.abs(tgt - prev_w).sum() / 2.0) if prev_w is not None else 0.0  # 第一天建倉成本已在各成員帳本扣過
        cost = turnover * RT_COST
        r = float(np.dot(tgt, R)) - cost
        rl = c["L"] * r - (c["L"] - 1.0) * MARGIN_RATE
        gross = tgt * (1.0 + np.array(R))
        s["w"] = (gross / gross.sum()).tolist() if gross.sum() > 0 else tgt.tolist()
        s["account"] = max(s["account"] * (1.0 + rl), 0.0)
        rec = {"date": d, "ret": round(rl, 8), "ret_1x": round(r, 8), "account": round(s["account"], 8), "L": c["L"],
               "members": members, "member_ret": [round(x, 8) for x in R], "target_w": [round(x, 4) for x in tgt],
               "weight_mode": wmode, "turnover": round(turnover, 4), "rebal_cost": round(cost, 6)}
        with led.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        s["last_date"] = d
        hist.append(R)
        done += 1
        print(f"{cid} {d} {c['L']}× {rl:+.2%}（1× {r:+.2%}，換手 {turnover:.1%}、成本 {cost:.3%}，{wmode}）")
    print(f"{cid}：本次寫入 {done} 天（成員 {'+'.join(members)}，可處理到 {cutoff}）")
    return done


def main() -> int:
    st = F12._rj(STATE, {})
    for cid, c in COMBOS.items():
        try:
            run_combo(cid, c, st)
        except Exception as e:  # 一個組合失敗不影響其他
            print(f"[warn] {cid} 合成失敗：{type(e).__name__}: {e}")
    F12._wj(STATE, st)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 十二節：自身失敗只印警告、exit 0
        import traceback
        traceback.print_exc()
        print(f"[warn] paper_opt_combo 失敗：{e}")
        sys.exit(0)
