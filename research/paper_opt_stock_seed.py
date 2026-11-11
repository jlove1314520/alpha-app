# -*- coding: utf-8 -*-
"""先.一五九-1（收件匣 043）紙上優化軌個股 S1～S4 的一次性「宇宙＋回測基準線」——零外部請求。

做什麼：
  1. 宇宙：讀 research/data/reaudit_ssu_loaded.pkl（#133 抽樣 236 檔，REAUDIT §5a 回測同一份）的代號，寫 stock_universe.json。
  2. 回測基準線：讀 research/data/reaudit_batch3_ext2025_cells/{因子}.json 裡 §5a「舊最優」那一格的 1× 引擎權益，
     用 reaudit_optimized_batch2_sector.overlay()（同 summarize()：槓桿付融資 6.5%、組合停損後冷卻 21 天領央行定存利率）
     套 L／組合停損，核對 2025 起段跟 §5a 表逐位一致；另算 S1 1.5×／2× 與「S1＋S3＋F14 各三分之一（2025 起、不再平衡）」。
  輸出（只在本機，research/data 不進 repo）：research/data/paper_opt/stock_universe.json、bt_stock.json。
用法：python research/paper_opt_stock_seed.py
非投資建議。
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = HERE / "data" / "paper_opt"
CELLS = HERE / "data" / "reaudit_batch3_ext2025_cells"
# id: (因子, 格 key, L, 組合停損, §5a 表 2025 起 年化／MDD（None＝表上沒有、只算不核對）)
SPEC = {
    "S1": ("f_revenue_surprise", "21_0_20_0.15_1", 1.0, 0.1, (0.449, -0.169)),
    "S1x15": ("f_revenue_surprise", "21_0_20_0.15_1", 1.5, 0.1, None),
    "S1x2": ("f_revenue_surprise", "21_0_20_0.15_1", 2.0, 0.1, None),
    "S2": ("f_short_term_reversal_1w", "21_0_30_1.0_-1", 3.0, 0.1, (0.400, -0.409)),
    "S3": ("f_ma_breakout", "21_0_10_0.15_1", 1.5, 0.1, (0.324, -0.266)),
    "S4": ("f_foreign_streak", "21_1_30_0.15_1", 1.0, 0.2, (0.222, -0.181)),
}
F14_KEY = "63_0_30_0.15"  # 紙上 paper_opt_f14.py 跑的原版 1×、不設組合停損


def main() -> int:
    data = pickle.loads((HERE / "data" / "reaudit_ssu_loaded.pkl").read_bytes())
    ids = sorted(data)
    del data
    # 同 reaudit_ext2025_engine.load_extended()：本機沒有 2025 起價格的檔（多為 ETF／債券 ETF）回測從 2024-11-15 起就不給分數，
    # 2025 起段等於不在宇宙裡；紙上照做（不然紙上會買到回測 2025 起段根本沒碰過的 ETF）。
    raw = HERE / "data" / "raw"
    excluded = []
    for sid in ids:
        f = raw / f"TaiwanStockPrice__{sid}__2025-01-01__latest.parquet"
        try:
            x = pd.read_parquet(f, columns=["date", "close"]) if f.exists() else pd.DataFrame()
        except Exception:  # noqa: BLE001
            x = pd.DataFrame()
        if x.empty or not ((x["date"].astype(str) > "2024-12-31") & (x["close"].astype(float) > 0)).any():
            excluded.append(sid)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stock_universe.json").write_text(json.dumps({"source": "research/data/reaudit_ssu_loaded.pkl（#133 抽樣，REAUDIT §5a 同一份）",
                                                         "ids": ids, "excluded_no_2025_price": excluded}, ensure_ascii=False), encoding="utf-8")
    print(f"宇宙 {len(ids)} 檔；本機無 2025 起價格、回測 2025 起段不給分數 {len(excluded)} 檔（紙上同樣排除）")

    import reaudit_optimized_batch2_sector as S
    sys.argv = [sys.argv[0], "--formula", "421"]
    import leveraged_bb90_backtest as LB
    LB.END = "2099-12-31"
    import reaudit_batch3_ext2025 as X

    out = {"curves": {}, "check": {}, "spec": {}}
    dates = None
    for sid_, (fac, key, L, stop, exp) in SPEC.items():
        c = json.loads((CELLS / f"{fac}.json").read_text(encoding="utf-8"))[key]
        ds = pd.to_datetime(pd.Series(c["dates"]))
        eq = np.array(c["equity"], float)
        eq = eq / eq[0]
        curve, n_stop = S.overlay(eq, LB.load_tw_rf_daily(ds), L, stop)
        pre = X._seg(curve, ds, pd.Timestamp("2015-01-01"), pd.Timestamp("2024-12-31"))
        post = X._seg(curve, ds, pd.Timestamp("2024-12-31"), ds.max())
        ok = None if exp is None else bool(abs(post["cagr"] - exp[0]) < 0.0005 and abs(post["mdd"] - exp[1]) < 0.0005)
        out["check"][sid_] = {"pre2025": {k: round(v, 4) for k, v in pre.items()}, "from2025": {k: round(v, 4) for k, v in post.items()},
                              "expect_from2025": exp, "ok": ok, "n_stop": n_stop, "trades": c["n_round_trips"]}
        out["spec"][sid_] = {"factor": fac, "key": key, "L": L, "stop": stop}
        out["curves"][sid_] = [round(float(x), 6) for x in curve]
        if dates is None:
            dates = [str(d.date()) for d in ds]
        elif dates != [str(d.date()) for d in ds]:
            raise SystemExit(f"{sid_} 日期軸跟前面不同，停止")
        print(f"{sid_} {fac} {key} L={L} 停損={stop}：2015～24 {pre['cagr']:+.1%}／{pre['mdd']:.1%}；2025 起 {post['cagr']:+.1%}／{post['mdd']:.1%}／Sharpe {post['sharpe']:.2f}"
              + ("" if exp is None else f"（表 {exp[0]:+.1%}／{exp[1]:.1%} → {'對上' if ok else '對不上'}）"))
    # 組合：S1＋S3＋F14 各三分之一，2025 起、起始各 1/3、不再平衡
    f14 = json.loads((HERE / "data" / "reaudit_ext2025_F14_cells.json").read_text(encoding="utf-8"))[F14_KEY]
    s14 = pd.Series(np.array(f14["equity"], float), pd.to_datetime(f14["dates"]))
    idx = pd.to_datetime(dates)
    parts = []
    for s in (pd.Series(out["curves"]["S1"], idx), pd.Series(out["curves"]["S3"], idx), s14):
        s = s[s.index >= "2024-12-31"]
        parts.append(s / s.iloc[0])
    cm = (sum(parts) / 3).dropna()
    g, m, sh = S.stats(cm.to_numpy(), cm.index.to_series().reset_index(drop=True))
    out["combo"] = {"dates": [str(d.date()) for d in cm.index], "curve": [round(float(x), 6) for x in cm],
                    "from2025": {"cagr": round(g, 4), "mdd": round(m, 4), "sharpe": round(sh, 4)}}
    print(f"S1＋S3＋F14 各 1/3（2025 起、不再平衡）：{g:+.1%}／{m:.1%}／Sharpe {sh:.2f}")
    out["dates"] = dates
    (OUT / "bt_stock.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"寫入 bt_stock.json（至 {dates[-1]}）")
    return 0 if all(v["ok"] is not False for v in out["check"].values()) else 1


if __name__ == "__main__" and "--factor-check" not in sys.argv:
    sys.exit(main())


def factor_check() -> int:
    """紙上因子（paper_opt_stock.frames，官方日檔＋price_history＋institutional_history）vs 回測延長資料
    （reaudit_ext2025_engine.load_extended＋reaudit_batch3_ext2025.recompute）在重疊日的前 N 名重疊率。結果寫進 bt_stock.json["factor_check"]。"""
    import paper_opt_f14 as F14
    import paper_opt_f17 as F17
    import paper_opt_stock as P
    import reaudit_batch3_ext2025 as X
    import reaudit_ext2025_engine as E
    ids = P.universe()
    F14.BARS = P.BARS
    bars, cal = F14.build_bars(ids)
    F17.REV_CACHE = P.OUT / "stock_rev_pre2025.json"
    fr = P.frames(ids, bars, P.foreign_shares(ids), F17.rev_frames(ids))
    ext, mk, miss, _j, end = E.load_extended()
    end = str(end.date())
    days = [d for d in ("2026-06-24", "2026-07-24", "2026-09-01", "2026-09-10", "2026-09-17", "2026-09-24") if d <= end and d in cal]
    res = {}
    for eid, (fac, _rb, _g, n, _p, dr) in P.ENGINES.items():
        X.FIN_MISMATCH.clear()
        X.recompute(ext, mk, fac)
        per = []
        for d in days:
            ref = {}
            for sid, df in ext.items():
                m = df["date"].astype(str).str[:10] == d
                if sid in fr and m.any() and df.loc[m, fac].notna().iloc[0]:
                    ref[sid] = float(df.loc[m, fac].iloc[0])
            pap = {sid: float(df.loc[df["date"] == d, fac].iloc[0]) for sid, df in fr.items()
                   if (df["date"] == d).any() and df.loc[df["date"] == d, fac].notna().iloc[0]}
            both = sorted(set(ref) & set(pap))
            tr = set(sorted(both, key=lambda s: -dr * ref[s])[:n])
            tp = set(sorted(both, key=lambda s: -dr * pap[s])[:n])
            rc = float(pd.Series([ref[s] for s in both]).rank().corr(pd.Series([pap[s] for s in both]).rank())) if len(both) > 2 else None
            per.append({"date": d, "n_ref": len(ref), "n_paper": len(pap), "n_both": len(both),
                        "top_overlap": round(len(tr & tp) / n, 3), "rank_corr": None if rc is None else round(rc, 4)})
            print(f"{eid} {fac} {d}：兩邊都有 {len(both)} 檔（回測 {len(ref)}／紙上 {len(pap)}）、前 {n} 名重疊 {len(tr & tp)}/{n}、排名相關 {rc}")
        res[eid] = per
    bt = json.loads((OUT / "bt_stock.json").read_text(encoding="utf-8"))
    bt["factor_check"] = {"days": days, "result": res}
    (OUT / "bt_stock.json").write_text(json.dumps(bt, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__" and "--factor-check" in sys.argv:
    sys.exit(factor_check())
