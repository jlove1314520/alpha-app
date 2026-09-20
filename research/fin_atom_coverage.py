"""財報原子覆蓋率統計（財報原子.覆蓋率，PENDING_QUEUE.md）。

純讀 `research/data/raw` 本機 parquet 快取，**不呼叫 load_dev/任何網路 API**
（load_dev 快取未命中會打 FinMind，這裡刻意繞過，直接讀檔）。
建表邏輯沿用 `FIN_ATOM_LIBRARY.build_quarter_frame`，不重寫。

輸出 `FIN_ATOM_COVERAGE.md`。可重複執行：python fin_atom_coverage.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RAW = HERE / "data" / "raw"
OUT = HERE / "FIN_ATOM_COVERAGE.md"
SUFFIX = "__2010-01-01__2024-12-31.parquet"  # 與 load_quarter_frame 的 load_dev 快取鍵一致

from FIN_ATOM_LIBRARY import ATOM_NAMES, build_quarter_frame  # noqa: E402

DS = {
    "inc": "TaiwanStockFinancialStatements",
    "bal": "TaiwanStockBalanceSheet",
    "cash": "TaiwanStockCashFlowsStatement",
}
FINANCIAL_INDUSTRIES = ("金融",)  # TaiwanStockInfo實際類別名：「金融業」「金融保險」（2026-09-20核對）


def _read(ds: str, sid: str):
    p = RAW / f"{ds}__{sid}{SUFFIX}"
    if not p.exists():
        return None
    try:
        return pd.read_parquet(p)
    except Exception as e:  # 壞檔不中斷整批，記錄後當作未快取
        print(f"WARN 讀取失敗 {p.name}: {e!r}")
        return None


def main() -> int:
    ids = sorted(p.name.split("__")[1] for p in RAW.glob(f"{DS['inc']}__*{SUFFIX}"))
    ids = sorted(set(ids))
    print(f"income快取股票數 {len(ids)}")

    info = pd.read_parquet(RAW / "TaiwanStockInfo__ALL__2000-01-01__2024-12-31.parquet")
    ind = dict(zip(info["stock_id"], info["industry_category"]))

    rows = []
    for sid in ids:
        inc, bal, cash = _read(DS["inc"], sid), _read(DS["bal"], sid), _read(DS["cash"], sid)
        if inc is None or inc.empty:
            continue
        try:
            fr = build_quarter_frame(inc, bal, cash)
        except Exception as e:
            print(f"WARN build_quarter_frame失敗 {sid}: {e!r}")
            continue
        rec = {"stock_id": sid, "industry": ind.get(sid, ""), "n_q": len(fr),
               "has_bal": bal is not None and not bal.empty,
               "has_cash": cash is not None and not cash.empty,
               "first": fr.index.min(), "last": fr.index.max()}
        for a in ATOM_NAMES:
            rec[f"n_{a}"] = int(fr[a].notna().sum())
            rec[f"first_{a}"] = fr.index[fr[a].notna()].min() if fr[a].notna().any() else pd.NaT
        rows.append(rec)
    df = pd.DataFrame(rows)
    df["is_fin"] = df["industry"].apply(lambda x: any(k in str(x) for k in FINANCIAL_INDUSTRIES))
    df["delisted_like"] = df["last"] < pd.Timestamp("2024-01-01")
    tot_q = df["n_q"].sum()

    def ratio(sub: pd.DataFrame, a: str) -> float:
        d = sub["n_q"].sum()
        return sub[f"n_{a}"].sum() / d if d else float("nan")

    L = ["# 財報原子覆蓋率（財報原子.覆蓋率）", "",
         "純讀本機快取（`research/data/raw/*__2010-01-01__2024-12-31.parquet`），**未呼叫任何API**；"
         "建表沿用`FIN_ATOM_LIBRARY.build_quarter_frame`。腳本：`fin_atom_coverage.py`（可重跑）。", "",
         f"- 股票數（有income快取且建表成功）：**{len(df)}**；股票-季度總列數：**{tot_q}**",
         f"- 同時有資產負債表快取：{int(df['has_bal'].sum())} 檔（{df['has_bal'].mean():.1%}）；"
         f"有現金流量表快取：{int(df['has_cash'].sum())} 檔（{df['has_cash'].mean():.1%}）",
         f"- 金融業（產業名含「金融」：金融業/金融保險）：{int(df['is_fin'].sum())} 檔；"
         f"末季<2024-01-01（下市/停止申報代理）：{int(df['delisted_like'].sum())} 檔", "",
         "**注意**：「非NaN比例」＝該原子非NaN季度數÷該群組股票-季度總數。"
         "資產負債表/現金流量表原子的NaN有兩種成因——(A)該股票這兩張表**根本沒有快取**（本機缺檔，非資料本身缺）、"
         "(B)有快取但該科目未申報。下表另列「僅限有該表快取者」的比例把兩者分開。", "",
         "## 1. 各原子非NaN比例", "",
         "| 原子 | 全體 | 僅限有該表快取者 | 非金融業 | 金融業 | 存續(末季≥2024) | 下市代理 | 最早可用期別(最小值) | 判定(<60%) |",
         "|---|---|---|---|---|---|---|---|---|"]
    src = {"revenue": "inc", "eps": "inc", "gross_profit": "inc", "op_income": "inc", "net_income": "inc",
           "shares": "inc", "ocf": "cash", "total_assets": "bal", "equity": "bal", "inventory": "bal",
           "receivable": "bal"}
    low = []
    for a in ATOM_NAMES:
        allr = ratio(df, a)
        s = src.get(a, "inc")
        sub = df if s == "inc" else df[df["has_bal" if s == "bal" else "has_cash"]]
        cond = ratio(sub, a)
        firsts = df[f"first_{a}"].dropna()
        flag = "**覆蓋不足**" if (not np.isnan(cond) and cond < 0.6) or allr < 0.6 else "OK"
        if flag != "OK":
            low.append((a, allr, cond))
        L.append(f"| `{a}` | {allr:.1%} | {cond:.1%} | {ratio(df[~df['is_fin']], a):.1%} | "
                 f"{ratio(df[df['is_fin']], a):.1%} | {ratio(df[~df['delisted_like']], a):.1%} | "
                 f"{ratio(df[df['delisted_like']], a):.1%} | "
                 f"{firsts.min().date() if len(firsts) else '—'} | {flag} |")

    L += ["", "## 2. 有原子資料的「股票」覆蓋（每檔至少一季非NaN）", "",
          "| 原子 | 有值股票數 | 占比 |", "|---|---|---|"]
    for a in ATOM_NAMES:
        n = int((df[f"n_{a}"] > 0).sum())
        L.append(f"| `{a}` | {n} | {n / len(df):.1%} |")

    L += ["", "## 3. 最早可用期別分布（income）", ""]
    yr = df["first"].dt.year.value_counts().sort_index()
    L.append("首季年度：" + "、".join(f"{int(y)}年{int(c)}檔" for y, c in yr.items()))

    L += ["", "## 4. 結論與分支", ""]
    if low:
        L.append("依交辦分支(a)：覆蓋率<60%的原子（全體口徑或限有該表快取口徑任一）：")
        for a, allr, cond in low:
            L.append(f"- `{a}`：全體{allr:.1%}／有快取者{cond:.1%} → **原子.五對該原子標「覆蓋不足」，不進IC地圖**"
                     f"（若肇因為(A)本機缺檔，可補抓後重評，補抓屬另案、受FinMind額度約束）。")
    else:
        L.append("所有原子覆蓋率≥60%，原子.五可全數納入。")
    L.append("")
    L.append("分支(b)：金融業存貨/應收整欄NaN屬預期（見第1節「金融業」欄），僅記錄，不列為缺陷。")
    n_all = len({p.name.split("__")[1] for p in RAW.glob(f"{DS['inc']}__*")})
    L += ["", "## 5. 查證發現（2026-09-20，人工核對2330原始type後寫入）", "",
          f"1. **股票數口徑**：交辦寫「約3,600檔」是快取**檔案數**；實際不同股票代號只有{n_all}檔有任一起點的income快取，"
          f"其中有`load_quarter_frame`鍵（起點2010-01-01）快取檔的是{len(ids)}檔，"
          f"但{len(ids) - len(df)}檔的income parquet為空或建表失敗，實際入統計{len(df)}檔；另{n_all - len(ids)}檔只有其他起點的快取，"
          "本統計與`load_quarter_frame`一律不涵蓋。",
          "2. **`net_income`／`shares`最早2013-03-31是定義造成，不是缺資料**：`net_income`取FinMind type"
          "`EquityAttributableToOwnersOfParent`（IFRS採用後才有），2012年以前（舊GAAP）只有`NetIncome`（無母公司歸屬拆分），"
          "兩者口徑不同，不可拼接。含這兩個原子的表達式，樣本起點須≥2013Q1；且`shares`＝net_income/EPS隨之同步。"
          "（若要往前延伸須另案決定是否接受口徑差異，此處不動定義。）",
          "3. **資產負債表/現金流原子低覆蓋的主因是本機缺檔（成因A）**：限有快取者的覆蓋率75%~85%，全體僅20%~31%。"
          "補抓受FinMind額度約束，屬另案；原子.五若要納入這些原子，樣本宇宙須先限縮為「三張表都有快取」的股票，"
          "並在報告揭露此限縮（存活者偏誤方向：下市代理的資產負債表覆蓋更低，見第1節）。",
          "4. 金融業`gross_profit`／`op_income`／`inventory`／`receivable`幾乎全NaN屬會計科目結構（金融業無此類科目），非缺陷；"
          "但本快取內金融類股票僅數檔（見開頭），金融業欄的比例樣本極小，僅供定性參考。"]
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"已寫入 {OUT}")
    print("\n".join(L[10:30]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
