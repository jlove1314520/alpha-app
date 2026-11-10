# -*- coding: utf-8 -*-
"""紙上優化軌（先.一五四-1，Cowork 收件匣 039 新軌道；不受前向模擬上限 14 限制）。

第 1 批（2026-11-06，cycle 20261106-173102）只做「骨架＋回測基準線」：
- 成員定義寫死在 MEMBERS（組合 C25／C20／C15＋單支最優 F11／F12／F16／F18／恐慌×PQ），參數照
  research/DRAWDOWN_FIX.md 1 節、3c 節與 PANIC_PQ_OPTIMIZED.md 2 節，這裡不調參。
- 回測曲線（App 畫虛線）從 research/data/drawdown_fix/curve_F*.csv 與 panic_pq/best_equity.npy 重算，
  組合照 drawdown_fix_combo.py 同一套算法（60 日反波動、每日再平衡、槓桿付台股融資 6.5%），並核對 DRAWDOWN_FIX
  記錄值（差距 >0.3 個百分點就標 reproduced=false，不往下用）。
- 紙上曲線（實線）**從起跑日（下一個交易日）開始記、不倒填**；每個成員要有「每日訊號產生器」才會有紙上日報酬。
  第 1 批還沒有任何產生器 → 紙上欄一律 status=NO_SIGNAL_GENERATOR、points=[]，**不拿回測或別的東西頂替**。
- 組合層再平衡成本：回測沒算；紙上版會照每日權重漂移的換手量 × 台股買賣腿成本計（產生器建好後才會有數字），
  看板 note 照實寫這個差異。美股成員紙上照實換匯（產生器建好時用 data/fx 牌告），回測沒換匯。

零外部請求（只讀本機 research/data 與 data/trading_calendar.json）；自身失敗只印警告、exit 0（十二節），
錯誤寫進輸出檔 last_error。輸出 data/paper_opt_track.json（App 研究室「紙上優化軌」區用，App 端另案）。
描述性、非判定、非投資建議；不寫 TRIALS_LEDGER（心跳寫 research/PROGRESS_HEARTBEAT.jsonl）。
用法：python research/paper_opt_track.py
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "research"
D = HERE / "data" / "drawdown_fix"
PQ = HERE / "data" / "panic_pq"
OUT = ROOT / "data" / "paper_opt_track.json"
CAL = ROOT / "data" / "trading_calendar.json"
TW = timezone(timedelta(hours=8))
MARGIN_RATE = 0.065 / 252.0  # 同 drawdown_fix_combo.py
CREATED = "2026-11-06"  # 本軌建立日（台北）；起跑日＝這天之後的第一個台股交易日
TOL = 0.003

# 單支：col＝curve CSV 欄位（best＝DRAWDOWN_FIX 1 節的降回撤版；F18 的 best＝只調槓桿 L'2.85 版）
SINGLES = {
    "F11": {"name": "F11 融資餘額 regime（B 崩盤段條件版）", "col": "best", "cagr": 0.477, "mdd": -0.386,
            "rule": "0050 曝險 3×、帳戶停損 30%；大盤<120日均線且距252日高點跌>20%→曝險×0.5", "market": "TW"},
    "F12": {"name": "F12 Weinstein 第二階段（B 版）", "col": "best", "cagr": 0.278, "mdd": -0.293,
            "rule": "台股個股 2×、帳戶停損 10%；大盤<120日均線且距252日高點跌>20%→曝險×0", "market": "TW"},
    "F16": {"name": "F16 美股價值 f_us_value_bm（C 波動目標版）", "col": "best", "cagr": 0.286, "mdd": -0.265,
            "rule": "美股只做多 1.55×、帳戶停損 20%；近60日實現波動目標 30%（上限 1×）", "market": "US"},
    "F18": {"name": "F18 零股委託簿失衡度（只調槓桿版）", "col": "best", "cagr": 0.244, "mdd": -0.230,
            "rule": "台股個股 2.85×、帳戶停損 10%，不加條件", "market": "TW"},
}
COMBOS = {
    "C25": {"name": "旗艦組合 C25（目標年化 25%）", "members": ["F11", "F12", "F15", "F16"], "L": 1.1,
            "cagr_1x": 0.237, "mdd_1x": -0.156, "mdd_L": -0.171},
    "C20": {"name": "組合 C20（目標年化 20%）", "members": ["F12", "F15", "F16"], "L": 1.05,
            "cagr_1x": 0.199, "mdd_1x": -0.144, "mdd_L": -0.151},
    "C15": {"name": "組合 C15（目標年化 15%）", "members": ["F12", "F14", "F16", "F17"], "L": 1.0,
            "cagr_1x": 0.155, "mdd_1x": -0.128, "mdd_L": -0.128},
}
PQ_REF = {"name": "恐慌×PQ 最優組", "cagr": 0.021, "mdd": -0.083,
          "rule": "鎖跌停比例≥20% 恐慌日、隔 1 日買 PQ strict 名單前 20 檔、高峰濾網、持有 120 日、個股停損 −15%、1×"}

NOTE = ("回測曲線（虛線）為樣本內兩層挑格的最優版，一定偏樂觀；資料只到 2024-12-31，holdout 未讀。"
        "回測的組合層沒算再平衡成本、美股成員沒換匯；紙上版（實線）會照實計再平衡成本並換匯，兩者差異照列。"
        "紙上從起跑日開始記、不倒填。非投資建議。")


def stats(curve: np.ndarray, dates: pd.DatetimeIndex) -> tuple[float, float]:
    yrs = (dates[-1] - dates[0]).days / 365.25
    cagr = float(curve[-1] ** (1 / yrs) - 1) if curve[-1] > 0 else -1.0
    mdd = float((curve / np.maximum.accumulate(curve) - 1).min())
    return cagr, mdd


def read_curve(fid: str, col: str = "orig") -> pd.Series:
    return pd.read_csv(D / f"curve_{fid}.csv", parse_dates=["date"]).set_index("date")[col]


def combo_curve(members: list[str], L: float) -> tuple[pd.Series, pd.Series]:
    """同 drawdown_fix_combo.py：成員原版曲線→日報酬、共同期間、60 日反波動（前一日）每日再平衡；回傳 1× 與 L× 曲線。"""
    R = pd.DataFrame({f: read_curve(f).pct_change() for f in members}).dropna()
    v = R.rolling(60, min_periods=60).std().shift(1)
    iv = 1 / v
    w = iv.div(iv.sum(axis=1), axis=0).fillna(1 / len(members))
    r = (R * w).sum(axis=1).to_numpy()
    idx = R.index.insert(0, R.index[0])
    c1 = np.concatenate([[1.0], np.cumprod(1 + r)])
    rl = L * r - (L - 1.0) * MARGIN_RATE
    cl = np.concatenate([[1.0], np.cumprod(1 + rl)])
    return pd.Series(c1, idx), pd.Series(cl, idx)


def weekly_points(s: pd.Series) -> list:
    """App 畫圖用：每週最後一個交易日一點（曲線正規化到起點 1.0），檔案不會太大。"""
    s = s / s.iloc[0]
    w = s.groupby(s.index.to_period("W")).tail(1)
    return [[d.strftime("%Y-%m-%d"), round(float(x), 4)] for d, x in w.items()]


def next_tw_trading_day(after: str) -> str:
    cal = json.loads(CAL.read_text(encoding="utf-8"))["tw"]
    d = date.fromisoformat(after) + timedelta(days=1)
    for _ in range(30):
        y = str(d.year)
        closed = set(cal.get(y, {}).get("closed", []))
        if d.weekday() < 5 and d.isoformat() not in closed:
            return d.isoformat()
        d += timedelta(days=1)
    raise RuntimeError("30 天內找不到交易日")


LEDGER_DIR = HERE / "data" / "paper_opt"


def paper_block(start: str, today: str, member: str | None = None) -> dict:
    """有每日產生器的成員（research/data/paper_opt/ledger_<id>.jsonl）就讀它畫紙上曲線（先.一五四-1a）。"""
    lp = LEDGER_DIR / f"ledger_{member}.jsonl" if member else None
    gen = HERE / f"paper_opt_{member.lower()}.py" if member else None
    if lp is not None and (lp.exists() or gen.exists()):
        rows = []
        for ln in (lp.read_text(encoding="utf-8").splitlines() if lp.exists() else []):
            try:
                r = json.loads(ln)
                rows.append((r["date"], float(r["ret"])))
            except Exception as e:  # 單行壞掉只略過，記警告
                print(f"[warn] {lp.name} 有一行讀不到：{e}")
        rows = [r for r in rows if r[0] >= start]
        if rows:
            eq = np.cumprod([1 + r for _, r in rows])
            dd = float((eq / np.maximum.accumulate(eq) - 1).min())
            yrs = len(eq) / 252
            cagr = float(eq[-1] ** (1 / yrs) - 1) if len(eq) >= 60 else None  # 未滿約 3 個月不年化〔自行裁量〕
            s = pd.Series(np.concatenate([[1.0], eq]),
                          pd.to_datetime([start] + [d for d, _ in rows]))
            return {"start": start, "status": "LIVE", "status_zh": f"紙上記帳中（{len(rows)} 個交易日，至 {rows[-1][0]}）",
                    "points": weekly_points(s), "cagr_to_date": None if cagr is None else round(cagr, 4),
                    "mdd_to_date": round(dd, 4), "total_return": round(float(eq[-1] - 1), 4), "days": len(rows)}
        status = "NOT_STARTED" if today < start else "GENERATOR_READY"
        msg = "產生器已上線，等起跑日後第一個交易日寫入" if status == "GENERATOR_READY" else "尚未起跑（起跑日前不記帳）；每日產生器已上線"
        return {"start": start, "status": status, "status_zh": msg, "points": [], "cagr_to_date": None, "mdd_to_date": None,
                "generator": f"research/paper_opt_{member.lower()}.py"}
    status = "NOT_STARTED" if today < start else "NO_SIGNAL_GENERATOR"
    msg = ("尚未起跑（起跑日前不記帳）" if status == "NOT_STARTED"
           else "每日訊號產生器尚未建好，紙上曲線從產生器上線那天起記，不倒填、不拿回測頂替")
    return {"start": start, "status": status, "status_zh": msg, "points": [], "cagr_to_date": None, "mdd_to_date": None}


def build() -> dict:
    today = datetime.now(TW).date().isoformat()
    start = next_tw_trading_day(CREATED)
    tracks, errs = [], []
    for cid, c in COMBOS.items():
        c1, cl = combo_curve(c["members"], c["L"])
        g1, m1 = stats(c1.to_numpy(), c1.index)
        gl, ml = stats(cl.to_numpy(), cl.index)
        ok = abs(g1 - c["cagr_1x"]) < TOL and abs(m1 - c["mdd_1x"]) < TOL and abs(ml - c["mdd_L"]) < TOL
        if not ok:
            errs.append(f"{cid} 重算對不上 DRAWDOWN_FIX：1× {g1:+.2%}/{m1:.2%}、{c['L']}× MDD {ml:.2%}")
        print(f"{cid} {'+'.join(c['members'])} 反波動 {c['L']}×：年化 {gl:+.2%}／MDD {ml:.2%}"
              f"（1× {g1:+.2%}／{m1:.2%}）→ {'對上' if ok else '對不上'}")
        tracks.append({"id": cid, "kind": "combo", "name": c["name"], "members": c["members"], "weight": "60 日反波動、每日再平衡",
                       "leverage": c["L"], "reproduced": ok,
                       "backtest": {"period": [str(cl.index[1].date()), str(cl.index[-1].date())], "cagr": round(gl, 4), "mdd": round(ml, 4),
                                    "points": weekly_points(cl) if ok else []},
                       "paper": paper_block(start, today, cid)})  # 先.一五四-1a：research/paper_opt_combo.py 寫 ledger_<cid>.jsonl
    for fid, s in SINGLES.items():
        cv = read_curve(fid, s["col"])
        g, m = stats(cv.to_numpy(), cv.index)
        ok = abs(g - s["cagr"]) < TOL and abs(m - s["mdd"]) < TOL
        if not ok:
            errs.append(f"{fid} 重算對不上 DRAWDOWN_FIX：{g:+.2%}/{m:.2%}")
        print(f"{fid}（{s['col']}）：年化 {g:+.2%}／MDD {m:.2%} → {'對上' if ok else '對不上'}")
        tracks.append({"id": fid, "kind": "single", "name": s["name"], "rule": s["rule"], "market": s["market"], "reproduced": ok,
                       "backtest": {"period": [str(cv.index[0].date()), str(cv.index[-1].date())], "cagr": round(g, 4), "mdd": round(m, 4),
                                    "points": weekly_points(cv) if ok else []},
                       "paper": paper_block(start, today, fid)})
    eq = np.load(PQ / "best_equity.npy")
    cal = pd.read_csv(PQ / "panic_daily.csv", usecols=["date"])["date"]
    cal = cal[(cal >= "2007-05-15") & (cal <= "2024-12-31")].reset_index(drop=True)
    pq = pd.Series(eq, pd.to_datetime(cal)) if len(cal) == len(eq) else None
    if pq is None:
        errs.append(f"PQ 日期 {len(cal)} 與權益 {len(eq)} 筆數不符")
        ok, g, m = False, None, None
    else:
        g, m = stats(pq.to_numpy(), pq.index)
        ok = abs(g - PQ_REF["cagr"]) < TOL and abs(m - PQ_REF["mdd"]) < TOL
        print(f"PQ：年化 {g:+.2%}／MDD {m:.2%} → {'對上' if ok else '對不上'}")
    tracks.append({"id": "PQ", "kind": "single", "name": PQ_REF["name"], "rule": PQ_REF["rule"], "market": "TW", "reproduced": ok,
                   "backtest": {"period": ["2007-05-15", "2024-12-31"], "cagr": None if g is None else round(g, 4),
                                "mdd": None if m is None else round(m, 4), "points": weekly_points(pq) if ok else []},
                   "paper": paper_block(start, today, "PQ")})
    return {"generated_at": datetime.now(TW).isoformat(timespec="seconds"), "track": "紙上優化軌（先.一五四-1）",
            "start": start, "note": NOTE, "tracks": tracks, "candidates": load_candidates(errs),
            "last_error": "；".join(errs) or None, "external_requests": 0}


CANDIDATES = ROOT / "research" / "data" / "paper_opt_candidates.json"


def load_candidates(errs: list) -> list:
    """候選欄（先.一五五-3：墓園重審第二批新進前 10 名，等 先.一五四 系列建每日訊號產生器後才正式上紙上）。
    來源 research/data/paper_opt_candidates.json（reaudit 腳本寫）；讀不到只記警告、回空清單（十二節）。"""
    try:
        if not CANDIDATES.exists():
            return []
        return json.loads(CANDIDATES.read_text(encoding="utf-8")).get("candidates", [])
    except (OSError, ValueError) as e:
        errs.append(f"候選欄讀取失敗 {type(e).__name__}")
        return []


def main() -> int:
    try:
        out = build()
    except Exception as e:  # noqa: BLE001 — 十二節：自身失敗只降級成警告
        print(f"[警告] paper_opt_track 失敗：{type(e).__name__}: {e}")
        prev = {}
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        prev["last_error"] = f"{datetime.now(TW).isoformat(timespec='seconds')} {type(e).__name__}: {e}"
        try:
            OUT.write_text(json.dumps(prev, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError as e2:
            print(f"[警告] 連錯誤都寫不進 {OUT}：{e2}")
        return 0
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"寫入 {OUT.relative_to(ROOT)}（{len(out['tracks'])} 支，起跑日 {out['start']}）；last_error={out['last_error']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
