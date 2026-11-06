# -*- coding: utf-8 -*-
"""先.一五五-2：把 reaudit_ext2025_batch1.json 寫成 REAUDIT_OPTIMIZED.md 的「3. 2025 起補跑」一節（標記之間整段取代）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOC = HERE / "REAUDIT_OPTIMIZED.md"
BEGIN, END_MARK = "<!-- EXT2025-BEGIN -->", "<!-- EXT2025-END -->"

# 還沒補跑的列：缺什麼、下一步（照實寫）
PENDING = [
    ("F7", "2025 起資料缺：`research/data/raw/TaiwanFuturesDaily__TX__2000-01-01__2024-12-31.parquet` 只到 2024-12-31，"
           "本機沒有 TX 2025 起日資料（`taifex_fut_yearly/` 也只到 2024.zip）。補法要新增請求（TAIFEX futDataDown 2025、2026 各 1 次，"
           "`taifex_www` 節流），依條目規定先寫提案，本輪不送。"),
    ("F8、F9、F12、F13、F14", "未跑（下一輪）：本機有 1,931 檔 `TaiwanStockPrice__*__2025-01-01__latest.parquet`，"
           "個股引擎價格由呼叫端傳入，可接上；需逐支改原腳本的 END 與讀檔路徑。"),
    ("F10、F11、F15、F16、F17、F18", "未跑（下一輪）：各自的訊號資料（廣度快取、MI_MARGN 週資料、`reaudit_us_prices.pkl`、重建臺灣50、TWTC7U）"
           "要逐一查 2025 起本機有沒有；美股 `reaudit_us_prices.pkl` 只到 2024-12，延長要重新批次下載 yfinance（新請求，先寫提案）。"),
]


def pct(x):
    return "—" if x is None else f"{x * 100:+.1f}%"


def row_seg(m):
    if not m:
        return "—", "—", "—"
    return pct(m["cagr"]), pct(m["mdd"]), f"{m['sharpe']:.2f}"


def fmt_params(p):
    return "，".join(f"{k}={v}" for k, v in p.items())


def build(d: dict) -> str:
    b = d["benchmark_0050"]
    L = [BEGIN, "", f"## 3. 2025 起補跑（先.一五五-2，Cowork 收件匣 039 已定案；保留資料已開放，先.一五五-1）", "",
         f"> 期間延長到 **{d['data_end']}**（0050 本機快取到 2026-11-06、VTI／IEF 快取到 2026-10-05，取共同終點）；"
         f"「2025 起段」＝{d['seg_start']}～{d['data_end']}，約 1.8 年。產生：{d['generated_at']}；程式 `research/reaudit_ext2025.py`"
         "（呼叫第一批同一支 `reaudit_optimized_batch1.py` 的網格與 simulate()，只用 `REAUDIT_END` 把終點延長）。"
         "**零新外部請求**：0050 2025 起讀本機 FinMind 快取原始收盤＋現金股利（除息日加回）＋2025-06-18 分割（188.65→47.16 參考價比值），"
         "其餘利率／匯率／美股 ETF 都是既有快取。性質仍是描述性，不是判定；非投資建議。", "",
         "**怎麼讀**：①欄是 2024 底以前挑出來的最優組**原封不動**往後跑——2025 起段那一欄完全沒拿來調參，是這張表裡最接近「樣本外」的數字；"
         "②欄是把 2025 起也放進去重新挑一次，一定比①好看（又多挑了一次），只當參考。", "",
         f"對照 0050 買進持有（含息）：全期年化 {pct(b['full']['cagr'])}、MDD {pct(b['full']['mdd'])}；"
         f"2025 起段年化 {pct(b['seg2025']['cagr'])}、MDD {pct(b['seg2025']['mdd'])}、Sharpe {b['seg2025']['sharpe']:.2f}。", "",
         "| 家族 | ①原最優組（不重調） | ① 2024 底前 年化／MDD | ① 2025 起段 年化 | ① 2025 起段 MDD | ① 2025 起段 Sharpe | ① 全期 年化／MDD | ②全期重新優化的參數 | ② 全期 年化／MDD／Sharpe | ② 2025 起段 年化／MDD | 天條一 | 曲線 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    flags = []
    for f in d["families"]:
        if "error" in f:
            L.append(f"| {f['id']} | 失敗：{f['error']} | | | | | | | | | | |")
            continue
        fx = f.get("fixed_seg2025") or {}
        pre = f.get("fixed_pre2025") or {}
        full = f.get("fixed_full") or {}
        ro, rs = f["reopt_full"], f.get("reopt_seg2025") or {}
        a, m, s = row_seg(fx)
        viol = []
        if fx and fx["mdd"] < -0.5:
            viol.append("①2025 起段 MDD>50%")
        if full and full.get("mdd", 0) < -0.5:
            viol.append("①全期 MDD>50%")
        if ro.get("violates_survival"):
            viol.append("②全期 MDD>50%")
        flags += [(f["id"], v) for v in viol]
        L.append(f"| {f['id']} {f['title']} | {fmt_params(f.get('fixed_params', {})) or f.get('fixed_missing', '—')} | "
                 f"{pct(pre.get('cagr'))}／{pct(pre.get('mdd'))} | {a} | {m} | {s} | {pct(full.get('cagr'))}／{pct(full.get('mdd'))} | "
                 f"{fmt_params(f['reopt_params'])} | {pct(ro['cagr'])}／{pct(ro['mdd'])}／{ro['sharpe']:.2f} | "
                 f"{pct(rs.get('cagr'))}／{pct(rs.get('mdd'))} | {'；'.join(viol) or '未越線'} | "
                 f"[png](data/reaudit_curves/ext2025_{f['id']}.png) |")
    L += ["", "**天條一（MDD>50%）**：" + ("；".join(f"{i} {v}" for i, v in flags) if flags else
                                        "本批 F1～F6 沒有任何一組（①或②）越過 50%，不用補 DRAWDOWN_FIX。"), ""]
    L += ["**還沒補跑的列（照實寫）**：", ""]
    L += [f"- {a}：{b}" for a, b in PENDING]
    L += ["", "**但書**：2025 起段只有約 1.8 年、是 0050 強勢上漲的一段（同段 0050 年化見上），任何只做多台股的組合在這段都會好看，"
          "不能拿這一段單獨證明策略有效；①欄的價值在於「沒調參也沒崩」，不是「贏多少」。美股（VTI）腿附存活者偏誤但書：**存活者偏誤未完全修正："
          "已下市股約 97%（抽樣 55／57）無價格來源。**（VTI 為指數 ETF，影響較小。）曲線 png 在本機 `research/data/reaudit_curves/ext2025_*.png`"
          "（該目錄不進公開 repo）。", "", END_MARK]
    return "\n".join(L)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    d = json.loads((HERE / "data" / "reaudit_ext2025_batch1.json").read_text(encoding="utf-8"))
    sec = build(d)
    doc = DOC.read_text(encoding="utf-8")
    if BEGIN in doc:
        a, rest = doc.split(BEGIN, 1)
        _, b = rest.split(END_MARK, 1)
        doc = a + sec + b
    else:
        doc = doc.rstrip("\n") + "\n\n" + sec + "\n"
    DOC.write_text(doc, encoding="utf-8")
    print(sec)


if __name__ == "__main__":
    main()
