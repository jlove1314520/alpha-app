# -*- coding: utf-8 -*-
"""先.一五四-1a ⑤ 紙上優化軌 F16（美股價值 f_us_value_bm，只做多）每日訊號產生器——研究帽產物，零外部請求。

兩個版本同一份底層、各記一條報酬（這裡不調參）：
  - ret（單支 F16 紙上曲線＝DRAWDOWN_FIX 1 節 C 波動目標版）：曝險＝1.55×min(1, 30%÷1× 底層近 60 日年化實現波動)
    （前一日資訊；不足 60 日 → 係數 1，同 drawdown_fix.cond_series）；未投入部分領 DTB3、超過 1 倍付 DTB3＋1.5%；
    帳戶自高點回撤 20% 清倉 21 個交易日（drawdown_fix.overlay()）。
  - ret_orig（組合 C25／C20／C15 的成員曲線＝原版）：reaudit_optimized_batch2_us_value.json best_by_calmar
    ＝lowvol_filter 0、N 25、rebalance 126、L 1.5、stop 0.20（原腳本 overlay：L×底層−(L−1)×(DTB3＋1.5%)，停損退現金 21 日）。
  底層（1× 無停損）：換股日 t 收盤，B/M＝每股帳面價值（SEC XBRL companyfacts，us_factors_value.book_value_per_share_pit，
    pit_date ≤ t 的最新一筆）÷ t 日還原收盤；B/M>0 且當日有報酬者取最高 25 檔等權；t+1 收盤成交（換手×0.10%）。
  換股相位〔自行裁量〕：從起跑日（2026-11-09 後第一個美股交易日）起每 126 個美股交易日。
帳面價值〔自行裁量〕：只讀本機 SEC 快取（research/data/raw/SEC_companyfacts_*.json，2026-11-05 抓），**強制不連網**
  （本檔執行期把快取有效期調成無限、requests 一律拋例外）——比換股日舊幾天只會「慢」不會「偷看」。
  下一次換股約 2027-05 前要更新快取，另案提案（PENDING_QUEUE 先.一五四-1e），快取過舊就照實在帳本標 bm_cache_age_days。
價格／匯率／DTB3：同 paper_opt_f15（research/data/paper_opt/us_returns.json）。ledger 的 ret／ret_orig 都是台幣報酬，另記美元。
**存活者偏誤未完全修正：已下市股約 97%（抽樣 55／57）無價格來源。** 宇宙為今天還在的 248 檔分層抽樣，偏樂觀。
輸出（append-only）：research/data/paper_opt/ledger_F16.jsonl、state_F16.json；起跑日 2026-11-09。
用法：python research/paper_opt_f16.py [--probe]
十二節：失敗只印警告、exit 0。非投資建議。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paper_opt_f15 as F15  # noqa: E402  （共用 rf／匯率／資料路徑）

OUT = F15.OUT
LEDGER = OUT / "ledger_F16.jsonl"
STATE = OUT / "state_F16.json"
START = "2026-11-09"
N, REB, COST, SPREAD, COOLDOWN = 25, 126, 0.0010, 0.015, 21
L_ORIG, STOP_ORIG = 1.5, 0.20
L_BEST, STOP_BEST, VOL_K, VOL_T = 1.55, 0.20, 60, 0.30


def _offline_sec():
    """執行期封網：SEC 快取視為永遠有效，任何 requests 呼叫直接拋例外（零外部請求的保證）。"""
    import requests
    import sec_edgar_client as S

    def _no_net(*a, **k):
        raise RuntimeError("paper_opt_f16 封網：不得送外部請求")
    S._CACHE_MAX_AGE_SECONDS = 10 ** 12
    requests.get = _no_net
    requests.post = _no_net
    requests.Session.request = _no_net
    return S


def bm_at(day: str, closes: dict) -> tuple[dict, dict]:
    import pandas as pd
    S = _offline_sec()
    from us_factors_value import book_value_per_share_pit
    m = S.get_cik_map()
    out, info = {}, {"n_cik": 0, "n_bvps": 0, "latest_pit": None}
    for t, px in closes.items():
        if t == "SPY" or not px:
            continue
        cik = m.get(t) or m.get(t.replace("-", "."))
        if cik is None:
            continue
        info["n_cik"] += 1
        try:
            b = book_value_per_share_pit(t, cik_override=cik)
        except Exception as e:  # noqa: BLE001  單檔失敗只略過
            print(f"[warn] {t} 帳面價值讀不到：{e}")
            continue
        if b.empty:
            continue
        b = b[["pit_date", "book_value_per_share"]].dropna()
        b = b[pd.to_datetime(b["pit_date"]) <= pd.Timestamp(day)].sort_values("pit_date")
        if b.empty:
            continue
        info["n_bvps"] += 1
        lp = str(b["pit_date"].iloc[-1])[:10]
        info["latest_pit"] = max(info["latest_pit"] or lp, lp)
        out[t] = float(b["book_value_per_share"].iloc[-1]) / px
    f = HERE / "data" / "raw" / "SEC_companyfacts_0000320193.json"  # 以 AAPL 快取檔時間代表這批 11/05 快取的年齡
    info["cache_age_days"] = round((time.time() - f.stat().st_mtime) / 86400, 1) if f.exists() else None
    return out, info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    a = ap.parse_args()
    src = json.loads(F15.SRC.read_text(encoding="utf-8"))
    rets, fx, closes = src["returns"], src.get("fx_usd_twd", {}), src.get("closes", {})
    dates = sorted(d for d in rets if "SPY" in rets[d])
    rf = F15.rf_daily()
    borrow = rf + SPREAD / 252.0
    if a.probe:
        day = max(closes)
        bm, info = bm_at(day, closes[day])
        top = sorted(((v, t) for t, v in bm.items() if v > 0 and rets.get(day, {}).get(t) is not None), reverse=True)[:N]
        print(f"{day}：B/M 有值 {len(bm)} 檔（{info}）；前 {N}：{[t for _, t in top][:10]}…")
        return 0
    s = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {
        "start": START, "k": 0, "w": {}, "pending": None, "base_hist": [], "last_date": None,
        "orig": {"eq": 1.0, "peak": 1.0, "cool": 0}, "best": {"v": 1.0, "peak": 1.0, "cool": 0, "in_pos": True},
        "expo_next": L_BEST, "bm_info": None}
    done = 0
    for i, day in enumerate(dates):
        if day < s["start"] or (s["last_date"] and day <= s["last_date"]):
            continue
        prev = dates[i - 1]
        r = rets[day]
        w = s["w"]
        base_day = sum(wt * (r.get(t) or 0.0) for t, wt in w.items())
        if w:
            g = {t: wt * (1 + (r.get(t) or 0.0)) for t, wt in w.items()}
            w = {t: v / (1 + base_day) for t, v in g.items()} if (1 + base_day) > 0 else g
        cost = 0.0
        if s["pending"] is not None:
            tgt = s["pending"]
            cost = sum(abs(tgt.get(t, 0.0) - w.get(t, 0.0)) for t in set(tgt) | set(w)) * COST
            w, s["pending"] = tgt, None
        base = base_day - cost
        rebal = s["k"] % REB == 0
        if rebal:
            if day not in closes:
                print(f"[warn] {day} 沒有收盤價位，本期不換股")
            else:
                bm, info = bm_at(day, closes[day])
                s["bm_info"] = {"date": day, **info}
                ok = [(v, t) for t, v in bm.items() if v > 0 and r.get(t) is not None]
                if len(ok) >= N:
                    ok.sort(reverse=True)
                    s["pending"] = {t: 1.0 / N for _, t in ok[:N]}
                else:
                    print(f"[warn] {day} B/M 可選檔數 {len(ok)} < {N}，本期不換股")
        s["k"] += 1
        s["w"] = w
        # 原版（組合成員）
        o = s["orig"]
        e = L_ORIG
        if o["cool"] > 0:
            o["cool"] -= 1
            e = 0.0
        ro = (L_ORIG * base - (L_ORIG - 1.0) * borrow) if (e > 0 and o["eq"] > 0) else (rf if o["eq"] > 0 else 0.0)
        o["eq"] = max(o["eq"] * (1 + ro), 0.0)
        o["peak"] = max(o["peak"], o["eq"]) if e > 0 else o["eq"]
        evt_o = None
        if e > 0 and o["eq"] < o["peak"] * (1 - STOP_ORIG):
            o["cool"], o["peak"], evt_o = COOLDOWN, o["eq"], "account_stop"
        # C 波動目標版（單支）：今天用前一日算好的曝險
        b = s["best"]
        v0 = b["v"]
        if b["in_pos"]:
            ex = s["expo_next"]
            b["v"] *= 1.0 + ex * base - max(ex - 1.0, 0.0) * borrow + max(1.0 - ex, 0.0) * rf
        else:
            ex = 0.0
            b["v"] *= 1.0 + rf
        b["v"] = max(b["v"], 0.0)
        rb = b["v"] / v0 - 1.0 if v0 > 0 else 0.0
        evt_b = None
        if b["in_pos"]:
            b["peak"] = max(b["peak"], b["v"])
            if b["v"] < b["peak"] * (1 - STOP_BEST):
                b["in_pos"], b["cool"], evt_b = False, COOLDOWN, "account_stop"
        else:
            b["cool"] -= 1
            if b["cool"] <= 0:
                b["in_pos"], b["peak"] = True, b["v"]
        s["base_hist"] = (s["base_hist"] + [base])[-VOL_K:]
        f = 1.0
        if len(s["base_hist"]) >= VOL_K:
            hs = s["base_hist"]
            m = sum(hs) / VOL_K
            rv = math.sqrt(sum((x - m) ** 2 for x in hs) / (VOL_K - 1)) * math.sqrt(252)
            if rv > 0:
                f = min(1.0, VOL_T / rv)
        s["expo_next"] = L_BEST * f
        f1, f0 = F15.fx_at(fx, day), F15.fx_at(fx, prev)
        if s["last_date"] is None:
            f0 = f1
        ratio = (f1 / f0) if (f1 and f0) else 1.0
        rec = {"date": day, "ret": round((1 + rb) * ratio - 1.0, 8), "ret_orig": round((1 + ro) * ratio - 1.0, 8),
               "ret_usd": round(rb, 8), "ret_orig_usd": round(ro, 8), "fx": f1, "fx_ratio": round(ratio, 6),
               "fx_missing": not (f1 and f0), "base_1x": round(base, 8), "cost": round(cost, 6), "n_hold": len(w),
               "expo_today": round(ex, 4), "vol_factor_next": round(f, 4), "rebalance_decided": rebal,
               "bm_info": s["bm_info"] if rebal else None, "account_event": evt_b, "orig_account_event": evt_o}
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        s["last_date"] = day
        done += 1
        print(f"{day} 單支 {rb:+.2%}／原版 {ro:+.2%}（美元）　持股 {len(w)} 檔{'　換股已決定' if rebal else ''}")
    STATE.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    print(f"本次寫入 {done} 個交易日（起跑 {s['start']}，最後 {s['last_date']}）")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f"[warn] paper_opt_f16 失敗：{e}")
        sys.exit(0)
