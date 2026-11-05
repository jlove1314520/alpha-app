# -*- coding: utf-8 -*-
"""先.一五〇-2：把 panic_pq_backtest.py 的結果寫成 research/PANIC_PQ_OPTIMIZED.md＋曲線圖（零請求）。"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = HERE / "data" / "panic_pq"


def pct(x):
    return f"{x*100:+.1f}%"


def main():
    res = json.loads((OUT / "backtest_result.json").read_text(encoding="utf-8"))
    df = pd.read_csv(OUT / "grid_results.csv")
    b = res["best"]
    ok = df[~df["violates_survival"] & (df["n_trades"] >= 10)]
    top = ok.sort_values("calmar", ascending=False).head(15)
    l1 = ok[ok["L"] == 1.0].sort_values("calmar", ascending=False).head(5)
    hi = ok.sort_values("cagr", ascending=False).head(5)
    A = pd.DataFrame(res["ctlA"]); B = pd.DataFrame(res["ctlB"]); C = res["ctlC"]
    A1 = A[A["L"] == 1.0].sort_values("cagr", ascending=False)
    B1 = B[B["L"] == 1.0].sort_values("cagr", ascending=False)
    # 同參數的 A（同 N、名單、濾網、同 L）
    Am = A[(A["N"] == b["N"]) & (A["list"] == b["list"]) & (A["filt"] == b["filt"])]
    cols = ["theta", "k", "N", "H", "list", "filt", "tp", "sl", "L", "cagr", "mdd", "sharpe", "calmar", "n_trades", "events_used", "win"]

    def tbl(d, cs):
        lines = ["| " + " | ".join(cs) + " |", "|" + "---|" * len(cs)]
        for _, r in d.iterrows():
            cells = []
            for c in cs:
                v = r[c]
                if c in ("cagr", "mdd", "win"):
                    cells.append(pct(v) if pd.notna(v) else "—")
                elif c in ("sharpe", "calmar"):
                    cells.append(f"{v:.2f}")
                elif c in ("tp", "sl"):
                    cells.append("無" if v == 0 else pct(v))
                else:
                    cells.append(str(v))
            lines.append("| " + " | ".join(cells) + " |")
        return "\n".join(lines)

    ev = res["events"]
    md = f"""# PANIC_PQ_OPTIMIZED.md — 恐慌求生日買進 PQ 成長股：樣本內最優化結果（先.一五〇-2 第 2 步）

> 產生：{res['generated']}，`research/panic_pq_backtest.py`＋`research/panic_pq_report.py`，零網路請求，期間 {res['period'][0]}～{res['period'][1]}（holdout 2025+ 未讀）。
> 性質：**描述性樣本內最優化**（照 SPEC／先.一五〇-1 方針，不寫 TRIALS_LEDGER）；最優組是挑出來的，**一定偏樂觀**，要靠紙上前向驗證。非投資建議。
> 多重比較參考欄：引擎層 {res['n_grid_engine']} 格 × 槓桿 4 ＝ {res['n_grid_total']} 格；其中 {res['n_violates']} 格 MDD>50%（天條一 `VIOLATES_SURVIVAL`，不入選）。
> 選最優規則〔自行裁量，同 REAUDIT_OPTIMIZED〕：MDD≤50% 且交易筆數 ≥10，依 Calmar（年化÷|MDD|）排序。

## 1. 恐慌事件（鎖跌停比例 ≥θ，20 日內合併）
""" + "\n".join(f"- θ={float(k)*100:.0f}%：{len(v)} 次（{', '.join(v)}）" for k, v in ev.items()) + f"""

## 2. 最優一組
- θ={b['theta']*100:.0f}%、分批 k={int(b['k'])} 日、N={int(b['N'])} 檔、持有 H={int(b['H'])} 日、名單＝{b['list']}、高峰濾網＝{b['filt']}、止盈＝{'無' if not b['tp'] else pct(b['tp'])}、止損＝{'無' if not b['sl'] else pct(b['sl'])}、槓桿 {b['L']}×
- 年化 **{pct(b['cagr'])}**、MDD **{pct(b['mdd'])}**、Sharpe {b['sharpe']:.2f}、{int(b['n_trades'])} 筆、用到 {int(b['events_used'])} 個事件、勝率 {pct(b['win'])}、平均每筆 {pct(b['avg_trade'])}
- 成本 2×：年化 {pct(res['best_cost2x']['cagr'])}、MDD {pct(res['best_cost2x']['mdd'])}
- 每次事件買了什麼：""" + "; ".join(f"{t['event']}→{'、'.join(t['picks']) or '（名單空）'}" for t in res["best_trades"]) + f"""

## 3. 對照組
- **C 0050 買進持有（總報酬）**：年化 {pct(C['cagr'])}、MDD {pct(C['mdd'])}、Sharpe {C['sharpe']:.2f}
- **A 不分恐慌、每季換 PQ 名單（同 N／名單／濾網）**：""" + "; ".join(f"{r.L}×：{pct(r.cagr)}／{pct(r.mdd)}" for r in Am.itertuples()) + f"""
  A 全部 1× 最好前 3：""" + "; ".join(f"N={r.N} {r.list}/{r.filt}：{pct(r.cagr)}／{pct(r.mdd)}" for r in A1.head(3).itertuples()) + f"""
- **B 只看恐慌、觸發後買 0050**（1× 前 3）：""" + "; ".join(f"θ={r.theta*100:.0f}% k={r.k} H={r.H}：{pct(r.cagr)}／{pct(r.mdd)}" for r in B1.head(3).itertuples()) + f"""

## 4. Calmar 前 15（MDD≤50%、≥10 筆）
{tbl(top, cols)}

## 5. 1× 前 5
{tbl(l1, cols)}

## 6. 年化最高前 5（MDD≤50%）
{tbl(hi, cols)}

## 7. 誠實但書
1. 恐慌事件很少（見 §1），最優組的成績靠少數幾次股災反彈；樣本內挑格在少事件下特別偏樂觀。
2. 恐慌指標只剩價格面（鎖跌停比例）；「無買盤」、CB 跌停、融資維持率、停資停券都沒有歷史（SPEC §4）。
3. 存活者偏誤：價格快取含部分已下市股但不保證完整（build_meta：401 檔最後成交早於 2024-06）。
4. 財報可得日用法規最晚日推定、寧晚勿早；停損止盈用收盤判斷。
5. 槓桿為每日重設的合成槓桿（融資 6.5%/年），3× 超過台股融資上限只當參考。
6. 圖：`research/data/panic_pq/curves/best_vs_0050.png`。

7. 事件數與 SPEC §5（38／33／18／11）不同：本檔期間從 2007-05-15 起，且「20 日內合併」以第一次觸發日起算、不因後續觸發而延長；SPEC §5 的計數口徑不同，以本檔為準。
8. 2007-12～2010-01 之間嚴格名單常是空的（金融海嘯期間幾乎沒有公司同時達到毛利、營益、營收、EPS 四個年增門檻），所以嚴格名單的格子等於自動躲過 2008；寬鬆名單在 2008 照買，回撤 −70% 以上——這是名單門檻的副作用，不是恐慌指標本身的功勞。

## 8. 描述性觀察（不是判定；做與判分離，判定留給驗證帽）
- 按風險調整報酬（Calmar）看，最優組 0.26 高於 0050 買進持有（約 {C['cagr']/abs(C['mdd']):.2f}），但年化只有 {pct(b['cagr'])}，因為一年裡大部分時間都持有現金。只看年化，1× 沒有任何一格贏過 0050。
- 最好的格子都集中在 θ=20%、k=1、H=120：等股災確認後隔日一次買進、抱半年。
- 對照 B（同樣的恐慌日改買 0050）1× 最好 {pct(B1.iloc[0]['cagr'])}；對照 A（不看恐慌、每季換名單）1× 最好 {pct(A1.iloc[0]['cagr'])}，但 MDD {pct(A1.iloc[0]['mdd'])}，超過天條一。

## 9. 變形方向（七之三：每個方向寫機制假設、需要的資料、資料是否免費、用哪段沒碰過的資料驗證）
1. **換條件：恐慌日之外也持有、恐慌日加碼**（核心持有 0050，恐慌日把一部分換成 PQ 名單）。機制：解決「大部分時間空手」的年化拖累。資料：現有。免費。驗證：2025+ 前向紙上（holdout 不碰）。
2. **換工具：恐慌日買台指期／正 2 ETF，而不是個股**。機制：股災反彈是全市場的 beta，個股名單常常是空的。資料：TAIFEX 歷史年度檔（已有快取）、00631L。免費。驗證：前向紙上。
3. **換條件：把融資維持率／停資停券加進恐慌指標**（目前只用價格）。機制：文章說的是「被迫賣出」，融資斷頭才是真正的求生訊號。資料：BFI84U 只能從 2026-10-28 起每日累積；全市場融資餘額 MI_MARGN 2013 起有。免費。驗證：從 2026-10-28 起累積的前向資料。
4. **反向：恐慌日賣出 PQ 名單裡的高峰循環股**（高峰濾網剔除的那些）。機制：景氣高峰股在股災後補跌。資料：現有。免費。驗證：前向紙上；含放空腿，需附借券資料缺陷但書。

## 10. 下一步
- 上紙上：前向模擬上限 14 已滿（CLAUDE.md 零之二⑤），本輪**不新增登記**，已把最優組寫進 `research/FORWARD_CANDIDATES.md` 候選清單 N13；有名額時由 Cowork 挑。
- App 看板顯示回測 vs 紙上曲線屬開發帽，等紙上模擬開跑後另開一輪。
"""
    (HERE / "PANIC_PQ_OPTIMIZED.md").write_text(md, encoding="utf-8")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        cal = pickle.loads((OUT / "prices_wide.pkl").read_bytes())["cal"]
        s0 = next(i for i, d in enumerate(cal) if d >= res["period"][0])
        x = pd.to_datetime(cal[s0:])
        be = np.load(OUT / "best_equity.npy"); ce = np.load(OUT / "c0050_equity.npy")
        (OUT / "curves").mkdir(exist_ok=True)
        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.plot(x, be, label="best (panic x PQ)")
        ax.plot(x, ce, label="0050 buy&hold")
        ax.set_yscale("log"); ax.legend(); ax.grid(alpha=.3)
        ax.set_title("Panic-day PQ growth: in-sample best vs 0050 (2007-05~2024-12)")
        fig.tight_layout(); fig.savefig(OUT / "curves" / "best_vs_0050.png", dpi=110)
    except Exception as e:
        print(f"[warn] 畫圖失敗：{e}")
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
