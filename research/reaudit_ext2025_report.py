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
    ("F8", "2025 起資料缺：訊號 f_short_sale_utilization 來自逐檔 `TaiwanStockMarginPurchaseShortSale`，本機 1,058 檔快取全部截在 "
           "`__2024-12-31.parquet`、沒有任何 2025 起檔；補要新增 FinMind 請求（236 檔×1 次，這台電腦 FinMind 402），依條目規定先寫提案，本輪不送。"),
    ("F9", "2025 起資料缺：訊號讀 `research/data/sector_flow_daily_gate73.parquet`（只到 2024-12-31），其來源逐檔三大法人 "
           "`TaiwanStockInstitutionalInvestorsBuySell` 本機沒有 2025 起快取；同 F8 要新請求，先寫提案。"),
    ("F11", "2025 起資料缺：訊號讀 `margin_debt_market_client.load_all_cached()`（`MARGIN_*.parquet` 週快取，607 筆、2012-05-04～2024-12-31，"
            "沒有任何 2025 起檔）；本機 `data/margin_maintenance.json` 的全市場融資金額只從 2026-08-25 起、`data/margin_by_stock_history.json` 只從 2026-09-29 起，"
            "接不上 2025-01～2026-08。補要新增 TWSE MI_MARGN 請求（約 90 週×1 次，`twse_rwd` 節流），依條目規定先寫提案，本輪不送。"),
    ("F18", "2025 起資料缺：訊號讀 `research/data/raw_twse_odd_lot/TWTC7U_YYYYMMDD.parquet`（1,092 檔，2020-10-26～2024-12-31，沒有任何 2025 起檔）；"
            "補要新增 TWTC7U 請求（2025-01～今約 440 個交易日×1 次），依條目規定先寫提案，本輪不送。"),
    ("F15、F16", "2025 起資料缺：美股價格 `research/data/reaudit_us_prices.pkl` 只到 2024-12；延長要重新批次下載 yfinance（新請求，先寫提案）。"),
    ("F17、PQ", "未跑（下一輪）：F17 要把重建臺灣50 量尺（`core_tilt_v2_stage1.py`）與 A_4pass 分數延長到 2025 起，先查它讀的市值／股數／因子快取 2025 起本機有沒有；"
            "PQ（先.一五〇-2 恐慌）同樣先查訊號資料。"),
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
                                        "F1～F6、F12～F14 沒有任何一組（①或②）越過 50%（F12 全期 -48.1% 逼近，見 3b）；"
                                        "**F10 原最優組（3 倍）全期 MDD -51.7% 越過天條一**（2025 起段本身 -32.8%，是 2024 高點延續到 2025-04 的回撤疊加），見 3c 與 `DRAWDOWN_FIX.md` 第 6 節。"), ""]
    L += _engine_rows()
    L += _breadth_rows()
    L += ["**還沒補跑的列（照實寫）**：", ""]
    L += [f"- {a}：{b}" for a, b in PENDING]
    L += ["", "**但書**：2025 起段只有約 1.8 年、是 0050 強勢上漲的一段（同段 0050 年化見上），任何只做多台股的組合在這段都會好看，"
          "不能拿這一段單獨證明策略有效；①欄的價值在於「沒調參也沒崩」，不是「贏多少」。美股（VTI）腿附存活者偏誤但書：**存活者偏誤未完全修正："
          "已下市股約 97%（抽樣 55／57）無價格來源。**（VTI 為指數 ETF，影響較小。）曲線 png 在本機 `research/data/reaudit_curves/ext2025_*.png`"
          "（該目錄不進公開 repo）。", "", END_MARK]
    return "\n".join(L)


ENGINE_FAMS = [
    ("F12", "#11／#393 Weinstein 第二階段（台股個股，引擎版）", ("ma", "market_gate", "top_n", "pos_stop", "rebalance_days", "L", "stop"),
     "+26.6%／-30.1%", "ma_gate_topN_個股停損"),
    ("F13", "#16／#17 f_quality_roe_stability 最高 N 檔（台股個股，只做多頭半邊）", ("rebalance_days", "market_gate", "top_n", "pos_stop", "L", "stop"),
     "+4.5%／-11.4%", "換股日_gate_topN_個股停損"),
    ("F14", "#475／#483 ML 價量選股（HGB 逐年重訓，台股個股，引擎版）", ("horizon_eq_rebalance_days", "market_gate", "top_n", "pos_stop", "L", "stop"),
     "+10.9%／-13.1%", "標籤期_gate_topN_個股停損"),
]

ENGINE_NOTES = {
    "F13": "**F13 怎麼讀**：原最優組（63 日換股、大盤閘門、20 檔、個股停損 15%、1 倍、組合止損 20%）在沒調參的 2025 起段年化 +12.0%、MDD -19.5%、Sharpe 0.91，"
           "比 2024 底前（+4.5%／-11.4%）好，但遠落後同段大盤；2025 起段的回撤（-19.5%）比 2024 底前整段最深（-11.4%）還深，全期 MDD 因此變成 -19.5%。"
           "全期重新優化挑到 21 日換股＋10% 組合止損，2025 起段 +26.6%／-12.8%——又是重新挑過才好看，只當參考。只做多頭半邊，原版多空數字含放空腿、屬資料缺陷。",
    "F14": "**F14 怎麼讀**：原最優組（標籤期＝換股 63 日、不設大盤閘門、30 檔、個股停損 15%、1 倍、組合止損 20%）在沒調參的 2025 起段年化 +22.2%、MDD -17.0%、"
           "Sharpe 1.33，Sharpe 跟 2024 底前（1.30）差不多，是這批個股家族裡 2025 起段最穩的一支；2025、2026 兩個測試年的模型都只用標籤到期日早於當年 1/1 的樣本重訓"
           "（2015～2024 沿用原分數檔），10 個價量特徵重算後在 2024 底前與原快取 236 檔全部一致。全期重新優化只把組合止損從 20% 改成 10%，2025 起段幾乎一樣（+22.3%／-14.3%）——"
           "代表這個家族對參數不敏感，跟 F12 相反。仍落後同段大盤（+53.9%），好處在回撤。",
    "F10": "**F10 怎麼讀**：原最優組（MA250 廣度<40% 就全數出場、月頻、3 倍、組合止損 30%）在沒調參的 2025 起段年化 -2.0%、MDD -32.8%，同段 0050 +65.1%——"
           "廣度在 2025-04 關稅急跌時跌破 40%、月頻訊號讓它在低點附近出場又沒趕上反彈；全期 MDD 從 -48.2% 擴大到 **-51.7%，越過天條一（VIOLATES_SURVIVAL）**。"
           "同一個訊號降到 2 倍、不加止損：全期 +20.1%／-39.3%、2025 起段 +5.3%／-29.6%（壓回 50% 內，見 `DRAWDOWN_FIX.md` 第 6 節）。"
           "全期重新優化（MA200、門檻 40%、防禦曝險 25%、2 倍、不止損）全期 +25.9%／-39.3%、2025 起段 +60.5%／-29.6%，但那是又挑一次的結果。"
           "交易次數很少（原版 11 筆），結論取決於少數幾次出場時點，過擬合風險高。",
    "F12": "**F12 怎麼讀**：原最優組（2 倍融資＋10% 組合止損）在沒調參的 2025 起段年化 +13.2%、MDD -35.8%，明顯落後同段大盤；"
           "全期 MDD 從 -30.1% 擴大到 -48.1%（回撤從 2024 年高點延續到 2025 年），離天條一 50% 只剩約 2 個百分點。"
           "全期重新優化挑到 3 倍＋個股停損 15%，但它在 2025 起段只有 +2.8%、MDD -42.6%——重新優化換來的是更差的 2025 段，"
           "代表 F12 的最優格對參數很敏感。融資倍數越高、2025 起段回撤越深（2 倍 -35.8%、重新優化的 3 倍 -42.6%）；要上紙上的話建議先用 1 倍版觀察〔自行裁量建議，未驗證〕。",
}


def _breadth_rows():
    """F10 全市場廣度 regime（reaudit_ext2025_breadth.py 的輸出）。"""
    p = HERE / "data" / "reaudit_ext2025_F10.json"
    if not p.exists():
        return []
    e = json.loads(p.read_text(encoding="utf-8"))
    pre, sg, fu, ro, rs, bm = e["fixed_pre2025"], e["fixed_seg2025"], e["fixed_full"], e["reopt_full"], e["reopt_seg2025"], e["bench_0050"]
    worst = min(fu["mdd"], sg["mdd"], ro["mdd"])
    flag = "**越線（VIOLATES_SURVIVAL）**" if worst < -0.5 else ("**MDD 逼近 50%（未越線）**" if worst < -0.45 else "未越線")
    fp = {k: v for k, v in e["fixed_params"].items()}
    return ["### 3c. 0050 曝險 regime 家族：F10 全市場廣度（`research/reaudit_ext2025_breadth.py`，零新外部請求）", "",
            f"期間 {e['data_start']}～{e['data_end']}（廣度面板本機 2025 起快取的終點，0050 同上節接法）；廣度面板＝原版 "
            f"`TaiwanStockPrice__*__2010-01-01__2024-12-31.parquet` 的 4 位數代號 {e['panel_n']} 檔，2025 起接同代號的 "
            f"`__2025-01-01__latest.parquet`（{e['panel_n_2025']} 檔有 2025 起價格；同原版用未還原收盤、今天仍在的名冊，存活者偏誤未修正）。"
            f"網格同原版 {e['n_grid']} 格（其中 {e['n_violates']} 格 MDD>50%）。同期 0050 含息：全期 {pct(bm['full']['cagr'])}／{pct(bm['full']['mdd'])}；"
            f"2025 起段 {pct(bm['seg2025']['cagr'])}／{pct(bm['seg2025']['mdd'])}。", "",
            "| 家族 | ①原最優組（不重調） | ① 2024 底前 年化／MDD（原表） | ① 2025 起段 年化 | ① 2025 起段 MDD | ① 2025 起段 Sharpe | ① 全期 年化／MDD | ②全期重新優化 | ② 全期 年化／MDD／Sharpe | ② 2025 起段 年化／MDD | 天條一 | 曲線 |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
            f"| F10 #248 全市場廣度 regime（0050 曝險） | {fmt_params(fp)} | {pct(pre['cagr'])}／{pct(pre['mdd'])}（+31.0%／-48.2%） | "
            f"{pct(sg['cagr'])} | {pct(sg['mdd'])} | {sg['sharpe']:.2f} | {pct(fu['cagr'])}／{pct(fu['mdd'])} | {fmt_params(e['reopt_params'])} | "
            f"{pct(ro['cagr'])}／{pct(ro['mdd'])}／{ro['sharpe']:.2f} | {pct(rs.get('cagr'))}／{pct(rs.get('mdd'))} | {flag} | "
            "[png](data/reaudit_curves/ext2025_F10.png) |", ""] + ([ENGINE_NOTES["F10"], ""] if "F10" in ENGINE_NOTES else [])


def _engine_rows():
    """個股引擎家族（reaudit_ext2025_engine.py 的輸出，data/reaudit_ext2025_engine_{家族}.json）。"""
    loaded = []
    for fam, title, keys, orig, keyfmt in ENGINE_FAMS:
        p = HERE / "data" / f"reaudit_ext2025_engine_{fam}.json"
        if p.exists():
            loaded.append((fam, title, keys, orig, keyfmt, json.loads(p.read_text(encoding="utf-8"))))
    if not loaded:
        return []
    e0 = loaded[0][5]
    L = ["### 3b. 個股引擎家族（`research/reaudit_ext2025_engine.py`，零新外部請求）", "",
         f"期間 2015-01～{e0['end']}（本機個股 2025 起快取的共同終點）；宇宙同第二批 #133 抽樣 236 檔。2025 起價格讀 "
         "`TaiwanStockPrice__{代號}__2025-01-01__latest.parquet`，還原權息用「漲跌」欄（當日報酬＝收盤÷(收盤−漲跌)−1，"
         "TWSE 漲跌對除權息參考價計；0050 2025-06-18 分割日 47.57−0.41＝47.16＝官方參考價，已核對），從 2024 最後一筆還原價連乘；"
         f"還原後沒有任何單日超過 ±10.5%。〔自行裁量〕2024 底仍掛牌但本機沒有 2025 起價格的 {e0['missing_note']['n_missing']} 檔"
         "（多為 ETF／債券 ETF，例：0056、00878、00772B），從 2024-11-15 起不再給分數，讓它們在 12 月換股就賣出；"
         "2025 起實際交易到這些檔："
         + "、".join(f"{f} {len(e['missing_note']['traded_2025'])} 檔" for f, *_, e in loaded)
         + "。同段加權指數（價格、不含息）2025-01～2026-09-24 年化 +53.9%、MDD -26.7%。"
         "F13 的 2025 起 ROE 穩定度用 `research/reaudit_ext2025_roe_factor.py` 以本機財報快取照原公式重算（PIT＝法定期限，Q4＝次年 3/31），"
         "2024 底以前沿用原欄位〔自行裁量：重算值有 4 檔在 2024 下半年與原值小幅不同，為保持與原表可比不覆蓋〕。", "",
         "| 家族 | ①原最優組（不重調） | ① 2024 底前 年化／MDD（原表） | ① 2025 起段 年化 | ① 2025 起段 MDD | ① 2025 起段 Sharpe | ① 全期 年化／MDD | ②全期重新優化 | ② 全期 年化／MDD／Sharpe | ② 2025 起段 年化／MDD | 天條一 | 曲線 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for fam, title, keys, orig, keyfmt, e in loaded:
        fp = {k: e["fixed_params"][k] for k in keys}
        pre, sg, fu, ro, rs = e["fixed_pre2025"], e["fixed_seg2025"], e["fixed_full"], e.get("reopt", {}), e.get("reopt_seg2025", {})
        worst = min(fu["mdd"], ro.get("mdd", 0), sg["mdd"])
        flag = "**越線（VIOLATES_SURVIVAL）**" if worst < -0.5 else ("**全期 MDD 逼近 50%（未越線）**" if worst < -0.45 else "未越線")
        L.append(f"| {fam} {title} | {fmt_params(fp)} | {pct(pre['cagr'])}／{pct(pre['mdd'])}（{orig}） | "
                 f"{pct(sg['cagr'])} | {pct(sg['mdd'])} | {sg['sharpe']:.2f} | {pct(fu['cagr'])}／{pct(fu['mdd'])} | "
                 f"key={ro.get('key')}（{keyfmt}），L={ro.get('L')}，stop={ro.get('stop')} | "
                 f"{pct(ro.get('cagr'))}／{pct(ro.get('mdd'))}／{ro.get('sharpe', 0):.2f} | {pct(rs.get('cagr'))}／{pct(rs.get('mdd'))} | {flag} | "
                 f"[png](data/reaudit_curves/ext2025_{fam}.png) |")
    L.append("")
    for fam, *_ in loaded:
        if fam in ENGINE_NOTES:
            L += [ENGINE_NOTES[fam], ""]
    return L


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
