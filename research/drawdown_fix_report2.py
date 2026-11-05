"""先.一五二-1b 第二段報告：由 drawdown_fix_report.py 呼叫 render(w, pct, num)，寫進 DRAWDOWN_FIX.md 第 4 節。
讀：research/data/drawdown_fix/{trades_F12.json, trades_F14.json, hedge.json, pq.json}（缺檔就照實寫未做）。"""
from __future__ import annotations

import json
from pathlib import Path

D = Path(__file__).resolve().parent / "data" / "drawdown_fix"


def _j(name):
    p = D / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def render(w, pct, num):
    w("## 4. 第二段（先.一五二-1b）：個股層歸因、個股停損／產業上限、台指期避險、恐慌 PQ")
    w("")
    w("程式：`research/drawdown_fix_trades.py`（①②，引擎只呼叫不改）、`research/drawdown_fix_hedge.py`（③）、"
      "`research/drawdown_fix_pq.py`（④）、`research/drawdown_fix_trades_f18.py`（F18 ①）、本節由 `research/drawdown_fix_report2.py` 產生。零外部請求、≤2024-12-31。")
    w("")
    # ---------- ① ----------
    w("### 4.1 個股層歸因（① 從引擎重跑最優格取 trades）")
    w("")
    w("做法：用 trades 重建每日持股股數 × `adj_close` 日變動＝每檔每日損益；在帳戶曲線（原版槓桿＋帳戶停損）最深 5 段裡彙總。"
      "「前 3 檔拖累」＝段內虧最多的 3 檔，數字是佔段起點 1× 引擎權益的比例；「跳空」＝開盤比前一日收盤低 ≥5% 那幾天的損失佔段內虧損合計；"
      "「出場太慢」＝段內單檔虧損超過一個等權部位的 20%；「跌停」＝段內引擎 trades 備註含跌停鎖住的筆數。〔自行裁量〕跳空與出場太慢門檻。")
    w("")
    for fid, fn in (("F12", "trades_F12.json"), ("F14", "trades_F14.json"), ("F18", "trades_F18.json")):
        t = _j(fn)
        if not t or "base" not in t:
            w(f"- {fid}：未做。")
            continue
        b = t["base"]
        a = b["at_orig"]
        w(f"**{fid}**（重建 {'對上' if b.get('reproduced') else '對不上'} REAUDIT：年化 {pct(a['cagr'])}／MDD {pct(a['mdd'], False)}，"
          f"槓桿 {a['L']}×、帳戶停損 {a['stop'] if a['stop'] is not None else '無'}；引擎 trades {b['n_trades']} 筆）")
        w("")
        w("| 段（起點→谷底） | 帳戶深度 | 同段 1× 引擎 | 前 3 檔拖累（佔權益） | 前 3 檔佔虧損 | 虧最多的產業（佔虧損） | 跳空佔虧損 | 出場太慢檔數 | 跌停筆數 |")
        w("|---|---|---|---|---|---|---|---|---|")
        for e in b["attribution"]:
            top = "、".join(f"{x['sid']}（{x['name_ind']}）{pct(x['pnl_pct_of_equity'], False)}" for x in e["top3"])
            w(f"| {e['peak']}→{e['trough']} | {pct(e['acct_depth'], False)} | {pct(e['engine_1x_ret'])} | {top} | "
              f"{pct(e['top3_share_of_loss'], False) if e['top3_share_of_loss'] is not None else '—'} | "
              f"{e['worst_industry']}（{pct(e['worst_industry_share_of_loss'], False) if e['worst_industry_share_of_loss'] is not None else '—'}） | "
              f"{pct(e['gap_loss_share'], False) if e['gap_loss_share'] is not None else '—'} | {e['slow_exit_n']} | {e['limit_locked_trades']} |")
        w("")
    w("**讀法（白話）**：")
    w("")
    w("- **F12 最深的一段（2022-09→2023-05，帳戶 −28%）幾乎全是單一檔 3678**：2021-05 以約 12 元（還原價）買進、漲到約 128 元，"
      "引擎**不會把漲多的贏家減回等權**，這檔長到約 4 成權益，之後跌回約 55 元才觸發 150 日均線出場，一檔就吃掉 24.8% 權益（佔該段虧損 76%）。"
      "這是「贏家不再平衡＋均線出場太慢」，**不是資料錯誤**（已逐日核對收盤／還原價）。對策方向＝單檔權重上限或換股日減回等權——"
      "引擎目前沒有這個選項，要改 `research/backtest/` 才做得到（十三節核心檔案，已寫提案交互動視窗，見 PENDING_QUEUE 先.一五二-1c）。")
    w("- **F12 2017-08→2018-03 那段（帳戶 −29%），同期 1× 引擎反而 +14%**：回撤是帳戶停損＋停手 21 日自己造成的（跟第 3b 節結論一致），個股層沒有可砍的東西。")
    w("- F12 其他三段：前 3 檔佔虧損 28～67%，跳空日佔虧損 70% 以上——動能小型股的虧損大多在開盤跳空時發生，個股停損擋不到（觸發後隔日開盤才成交）。"
      "跳空佔比用 `adj_open`／前日 `adj_close` 近似，未逐筆核對，只當方向參考。")
    w("- **F14 回撤本來就淺（−6%～−13%）、分散**：前 3 檔佔虧損多在 23～47%（2017-12 那段 2337 一檔佔 77% 但只 −6%），跳空佔 4～46%，"
      "沒有單一可砍的來源；**照實寫：砍不掉，也不需要砍**。")
    if _j("trades_F18.json"):
        w("- **F18（先.一五二-1d 補）虧損分散**：前 3 檔只佔各段虧損 18～43%，沒有單一產業超過 3 成；最深一段（2023-07→2024-12，帳戶 −25.4%）"
          "同期 1× 引擎反而 +2.5%，跟 F12 2017 那段同一種形狀——**3× 槓桿＋帳戶停損 10% 停手 21 日自己造成**，個股層沒有可砍的東西"
          "（第 1 節只調槓桿到 2.85× 就淺到 −23.0%，就是這個原因）。資料載入約 8.5 分鐘（本機快取）。")
        w("- 全部 15 段都沒有跌停賣不掉的筆數（引擎備註 0 筆）。")
    else:
        w("- 全部 10 段都沒有跌停賣不掉的筆數（引擎備註 0 筆）。F18 本輪未做（要重新載入零股因子資料），見 4.5。")
    w("")
    # ---------- ② ----------
    w("### 4.2 引擎新格：個股停損 10%、產業上限（② F12）")
    w("")
    t = _j("trades_F12.json")
    if t:
        names = {"base": "原版（無個股停損）", "stop10": "個股停損 10%（觸發隔日開盤成交＝跳空照實吃）",
                 "top20": "對照：每次只留分數前 20 名（不設產業上限）", "ind2": "產業上限 2 檔＋只留前 20 名",
                 "ind3": "產業上限 3 檔＋只留前 20 名", "ind2n": "產業上限 2 檔（不截名次）", "ind3n": "產業上限 3 檔（不截名次）"}
        w("| 格 | 引擎 trades | 原版槓桿／帳戶停損下 年化／MDD | 不設帳戶停損 年化／MDD | 調到原版年化的 L'／MDD |")
        w("|---|---|---|---|---|")
        for k, v in t.items():
            a = v["at_orig"]
            sc = {str(s["stop"]): s for s in v["scan"]}
            nost = sc.get("None")
            same = [s["same_cagr"] for s in v["scan"] if s["same_cagr"]]
            sbest = max(same, key=lambda x: x["mdd"]) if same else None
            w(f"| {names.get(k, k)} | {v['n_trades']} | {pct(a['cagr'])}／{pct(a['mdd'], False)} | "
              f"{pct(nost['atL0']['cagr']) + '／' + pct(nost['atL0']['mdd'], False) if nost else '—'} | "
              f"{(str(sbest['L']) + '×／' + pct(sbest['mdd'], False)) if sbest else 'L≤3 達不到'} |")
        w("")
        w("讀法：**個股停損 10% 與產業上限全都讓 F12 變差**。個股停損：同年化要加到 2.3×，MDD 反而 −46%（原版 −30%）——"
          "動能股常先跌 10% 再續漲，停損把之後的漲幅砍掉，跳空又讓停損在更低價成交。產業上限：引擎換股日會賣掉「不在名單內」的持股，"
          "所以「截到前 20 名」本身就強迫大量換股（交易數 683→1,385、年化掉到 +2.6%）；拆開後，不截名次的產業上限 2／3 檔仍是年化 +11%／+15%、"
          "MDD −44%／−41%，比原版差。F12 的回撤不是產業集中造成的（4.1 的大段來自單一檔或帳戶停損），所以產業上限砍不到。")
    else:
        w("未做。")
    w("")
    # ---------- ③ ----------
    w("### 4.3 台指期空單避險（③）")
    w("")
    h = _j("hedge.json")
    if h:
        w("避險腿＝台指期 TX 連續合約（還原）日報酬，h＝每 1 元多頭配 h 元期貨空單名目（前一日資訊決定、隨槓桿放大），"
          "換倉成本照 F7（萬分之 5／單邊）。版本：固定空 0.25／0.5／0.75 倍；台指期跌破 60／120／200 日均線才空 0.5／1 倍；"
          "跌破均線且距 252 日高點跌 >10／15／20% 才空（＝只在崩盤段避險）。× 原版帳戶停損／不停損，L' 掃到年化 ≥ 原版。")
        w("")
        w("| 家族 | 與台指期日報酬相關 | 原版 年化／MDD | 同年化下 MDD 最淺的避險版 | L' | MDD | 改善 |")
        w("|---|---|---|---|---|---|---|")
        for f in ("F12", "F14", "F17", "F18"):
            x = h.get(f)
            if not x or "orig" not in x:
                continue
            o, b = x["orig"], x.get("best")
            if b:
                s = b["same_cagr"]
                w(f"| {f} | {x['corr_r_tx']:.2f} | {pct(o['cagr'])}／{pct(o['mdd'], False)} | {b['desc']}（帳戶停損 {b['stop'] if b['stop'] is not None else '無'}） | "
                  f"{s['L']} | {pct(s['mdd'], False)} | {(s['mdd'] - o['mdd']) * 100:+.1f} 個百分點 |")
            else:
                w(f"| {f} | {x['corr_r_tx']:.2f} | {pct(o['cagr'])}／{pct(o['mdd'], False)} | L≤3 沒有版本達到原版年化 | — | — | — |")
        w("")
        w("讀法：**避險只在 F18 有一點用（−25.4%→−22.7%，跟第 1 節「只調槓桿」的 −23.0% 幾乎一樣，落在雜訊範圍），"
          "F12 只淺 0.8 個百分點，F14／F17 同年化下全部更深**。原因：避險同時砍掉多頭報酬，要加槓桿補回年化，加回去的槓桿把回撤又拉回來；"
          "F17 跟台指期相關 0.94，等於在做空自己。不要求同年化時，固定空 0.25 倍可把 F14 Sharpe 1.30→1.01、年化 10.9%→6.8%（MDD −13.5%，沒變淺）——"
          "**避險在這幾支都不是免費的降回撤**。")
        w("")
        w("> 資料缺陷但書（含空單腿）：期貨空單沒有借券問題，但轉倉價差用還原連續序列近似、未計逐筆滑價與保證金追繳，"
          "保證金機會成本假設由帳戶現金支應照領無風險利率〔自行裁量〕——數字偏樂觀。")
    else:
        w("未做。")
    w("")
    # ---------- ④ ----------
    w("### 4.4 恐慌 PQ（④ 先.一五〇-2 最優格）")
    w("")
    p = _j("pq.json")
    if p:
        o = p["orig"]
        w(f"底層＝PQ 最優格 1× 帳戶日權益（`research/data/panic_pq/best_equity.npy`），重建年化 {pct(o['cagr'])}／MDD {pct(o['mdd'], False)}（對上 PANIC_PQ_OPTIMIZED）；"
          f"大盤代理＝{p['market_proxy']}；有持股的日子只佔 {p['invested_share']:.0%}。條件 A～D、帳戶停損 10%、台指期避險共 {p['n_variants']} 版。")
        w("")
        w("最深 5 段：" + "；".join(f"{e['peak']}→{e['trough']} {pct(e['depth'], False)}（{e['cause']}）" for e in p["episodes"]))
        w("")
        w("結果：**沒有任何版本在同年化下比原版淺**（可達同年化的 {}/{} 版最淺仍是 {}）。".format(
            p["n_feasible"], p["n_variants"], pct(p["best"]["same_cagr"]["mdd"], False) if p["best"] else "—")
          + "原因很單純：PQ 最深才 −8.3%、35 筆交易、只用到 8 個恐慌事件，大盤條件與避險都在它空手時生效，"
          "**照實寫：砍不掉、交易太少**。")
    else:
        w("未做。")
    w("")
    w("### 4.5 第二段結論與尚未做")
    w("")
    w("- **結論**：個股停損、產業上限、台指期避險，在「報酬不縮水」的要求下**都沒有比第 1 節的大盤條件或第 3c 節的多策略組合更好**；"
      "F12 的大回撤來源是「贏家不再平衡（單檔長到 4 成）」與「帳戶停損自己造成」，前者要引擎加單檔權重上限才測得到。")
    if _j("trades_F18.json"):
        w("- **尚未做**：F12 單檔權重上限／換股日減回等權（要改引擎，交互動視窗：PENDING_QUEUE 先.一五二-1c）。F18 歸因已由先.一五二-1d 補上（`research/drawdown_fix_trades_f18.py`）。")
    else:
        w("- **尚未做**：F18 個股層歸因（要重新載入零股因子資料，`reaudit_optimized_batch2_oddlot.load_sample_with_factors`，下一輪做）；"
          "F12 單檔權重上限／換股日減回等權（要改引擎，交互動視窗：PENDING_QUEUE 先.一五二-1c）。")
    w("- **上紙上**：前向模擬上限 14／14 已滿（CLAUDE.md 零之二⑤），不新增登記；第二段沒有比第一段更好的降回撤版，`research/FORWARD_CANDIDATES.md` 候選 N14 不變。")
    w("")
