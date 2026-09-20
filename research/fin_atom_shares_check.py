"""財報原子.shares交叉驗證（PENDING_QUEUE.md）。純讀`research/data/raw`本機快取，不呼叫API。

兩項驗證：
(1) `shares`（=歸屬母公司淨利/EPS，加權平均股數）對照資產負債表`OrdinaryShare`（普通股股本，
    元）÷面額10＝期末普通股股數。**事前登記的判定口徑（跑之前寫死，不看結果調整）**：
    - 抽樣：同時有income與balance快取的股票，`random.Random(20260920)`抽200檔；
    - 逐「股票-季度」計算 rel_diff = |shares_eps − shares_bs| / shares_bs，兩者皆非NaN且EPS≠0才入樣；
    - 主判定量＝全部入樣股票-季度的 rel_diff **中位數**；<2%→維持現行定義，≥2%→標註shares不可用於每股化；
    - 敏感度（不影響主判定，僅並列）：剔除|EPS|<0.1（EPS四捨五入雜訊大）、每檔中位數的分布、
      面額非10元疑似股（每檔rel_diff中位數>50%）。
    偏誤方向誠實揭露：EPS加權平均股數 vs 期末股數本來就不同（期中增減資、庫藏股、特別股），
    此驗證量到的是「兩種股數口徑的差距」，不是「shares錯多少」。
(2) `ocf`兩個FinMind type（CashFlowsFromOperatingActivities / NetCashInflowFromOperatingActivities）
    在重疊期是否逐期相等（原本只驗過2330）：全部有現金流快取的股票、逐期比對。
輸出`FIN_ATOM_SHARES_CHECK.md`。可重跑：python fin_atom_shares_check.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RAW = HERE / "data" / "raw"
OUT = HERE / "FIN_ATOM_SHARES_CHECK.md"
SUFFIX = "__2010-01-01__2024-12-31.parquet"
SEED, SAMPLE_N, PAR_VALUE, THRESHOLD = 20260920, 200, 10.0, 0.02

from FIN_ATOM_LIBRARY import build_quarter_frame  # noqa: E402


def _read(ds: str, sid: str):
    p = RAW / f"{ds}__{sid}{SUFFIX}"
    if not p.exists():
        return None
    try:
        return pd.read_parquet(p)
    except Exception as e:  # 壞檔不中斷整批
        print(f"WARN 讀取失敗 {p.name}: {e!r}")
        return None


def _ids(ds: str) -> set[str]:
    return {p.name.split("__")[1] for p in RAW.glob(f"{ds}__*{SUFFIX}")}


def shares_check() -> tuple[pd.DataFrame, list[str]]:
    both = sorted(_ids("TaiwanStockFinancialStatements") & _ids("TaiwanStockBalanceSheet"))
    sample = sorted(random.Random(SEED).sample(both, min(SAMPLE_N, len(both))))
    rows = []
    for sid in sample:
        inc, bal = _read("TaiwanStockFinancialStatements", sid), _read("TaiwanStockBalanceSheet", sid)
        if inc is None or bal is None or inc.empty or bal.empty:
            continue
        try:
            fr = build_quarter_frame(inc, bal, None)
        except Exception as e:
            print(f"WARN build失敗 {sid}: {e!r}")
            continue
        o = bal[bal["type"] == "OrdinaryShare"].drop_duplicates("date", keep="last")
        if o.empty:
            continue
        bs = pd.Series(o["value"].astype(float).values / PAR_VALUE,
                       index=pd.to_datetime(o["date"]), name="shares_bs")
        eps = build_quarter_frame(inc, None, None)["eps"]
        j = pd.concat([fr["shares"].rename("shares_eps"), eps.rename("eps"), bs], axis=1, join="inner").dropna()
        j = j[(j["eps"] != 0) & (j["shares_bs"] > 0)]
        if j.empty:
            continue
        j = j.assign(stock_id=sid,
                     rel_diff=(j["shares_eps"] - j["shares_bs"]).abs() / j["shares_bs"])
        rows.append(j.reset_index().rename(columns={"index": "period_end"}))
    return (pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()), sample


def ocf_check() -> dict:
    n_stocks = n_overlap_rows = n_eq = n_only_a = n_only_b = 0
    diff_examples = []
    bad_stocks = set()
    for sid in sorted(_ids("TaiwanStockCashFlowsStatement")):
        c = _read("TaiwanStockCashFlowsStatement", sid)
        if c is None or c.empty:
            continue
        n_stocks += 1
        c = c.drop_duplicates(subset=["date", "type"], keep="last")
        piv = c.pivot(index="date", columns="type", values="value")
        a = piv.get("CashFlowsFromOperatingActivities")
        b = piv.get("NetCashInflowFromOperatingActivities")
        if a is None or b is None:
            n_only_a += int(a is not None and b is None)
            n_only_b += int(b is not None and a is None)
            continue
        both = pd.concat([a, b], axis=1, keys=["a", "b"]).dropna()
        n_overlap_rows += len(both)
        eq = np.isclose(both["a"].astype(float), both["b"].astype(float), rtol=1e-9, atol=0)
        n_eq += int(eq.sum())
        if not eq.all():
            bad_stocks.add(sid)
            for d, r in both[~eq].head(2).iterrows():
                diff_examples.append((sid, str(d), float(r["a"]), float(r["b"])))
    return {"n_stocks": n_stocks, "n_overlap_rows": n_overlap_rows, "n_equal": n_eq,
            "n_only_first_type": n_only_a, "n_only_second_type": n_only_b,
            "bad_stocks": sorted(bad_stocks), "examples": diff_examples[:10]}


def main() -> int:
    df, sample = shares_check()
    if df.empty:
        print("無可比對資料")
        return 1
    med = float(df["rel_diff"].median())
    filt = df[df["eps"].abs() >= 0.1]
    per_stock = df.groupby("stock_id")["rel_diff"].median()
    par_suspect = per_stock[per_stock > 0.5]
    branch = "維持現行定義（<2%）" if med < THRESHOLD else "標註shares不可用於每股化（≥2%）"
    q = df["rel_diff"].quantile([0.1, 0.25, 0.5, 0.75, 0.9, 0.99])
    oc = ocf_check()

    L = ["# 財報原子.shares交叉驗證", "",
         "純讀本機快取，**未呼叫任何API**。腳本：`fin_atom_shares_check.py`（可重跑，抽樣種子固定）。"
         "判定口徑在跑之前寫在腳本檔頭（事前登記），不是看結果後調整。", "",
         "## 1. shares（淨利/EPS，加權平均）vs 資產負債表`OrdinaryShare`÷面額10（期末普通股股數）", "",
         f"- 抽樣：同時有income與balance快取者，種子{SEED}抽{SAMPLE_N}檔；實際入樣 **{df['stock_id'].nunique()}檔／"
         f"{len(df)}個股票-季度**（{len(sample) - df['stock_id'].nunique()}檔因缺OrdinaryShare或無重疊期被排除）",
         f"- **主判定量：全部股票-季度 |shares_eps−shares_bs|/shares_bs 的中位數 = {med:.2%}**（門檻2%）→ "
         f"**{branch}**",
         "- rel_diff分位數：" + "、".join(f"P{int(k*100)}={v:.2%}" for k, v in q.items()),
         f"- 敏感度（不影響主判定）：剔除|EPS|<0.1後（{len(filt)}列）中位數 = {filt['rel_diff'].median():.2%}；"
         f"每檔中位數的中位數 = {per_stock.median():.2%}；每檔中位數<2%的股票占 {(per_stock < THRESHOLD).mean():.1%}",
         f"- 面額疑似非10元（每檔中位數>50%）：{len(par_suspect)}檔"
         + (f"（{', '.join(par_suspect.index[:10])}{'…' if len(par_suspect) > 10 else ''}）" if len(par_suspect) else ""),
         "",
         "**如何讀這個數字（誠實揭露）**：EPS加權平均股數本來就不等於期末股數（期中增減資、庫藏股、特別股、"
         "面額非10元的外國公司），這裡量到的是「兩種股數口徑的差距」，不是「shares錯了多少」。"
         "判定只回答一個問題：`shares`拿來當每股化分母是否安全。", "",
         "## 2. `ocf`兩個FinMind type在重疊期是否逐期相等（原本只驗過2330）", "",
         f"- 有現金流快取的股票：{oc['n_stocks']}檔；兩個type都存在的重疊「股票-期別」：{oc['n_overlap_rows']}列",
         f"- 逐期相等（rtol=1e-9）：**{oc['n_equal']}/{oc['n_overlap_rows']}**"
         + (f"（{oc['n_equal'] / oc['n_overlap_rows']:.4%}）" if oc["n_overlap_rows"] else ""),
         f"- 只有第一個type（CashFlowsFromOperatingActivities）的股票：{oc['n_only_first_type']}檔；"
         f"只有第二個type的股票：{oc['n_only_second_type']}檔",
         f"- 不相等的股票數：{len(oc['bad_stocks'])}" + (f"，例：{oc['examples']}" if oc["examples"] else ""), ""]
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
