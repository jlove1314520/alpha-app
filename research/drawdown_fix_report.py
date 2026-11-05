"""先.一五二-1：research/data/drawdown_fix/results.json → research/DRAWDOWN_FIX.md（零請求）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = Path(__file__).resolve().parent
RES = HERE / "data" / "drawdown_fix" / "results.json"
OUT = HERE / "DRAWDOWN_FIX.md"
ORDER = ["F11", "F18", "F12", "F16", "F15", "F14", "F10", "F17", "F2", "F7"]
KIND_ZH = {"none": "只調槓桿", "ma": "A 大盤均線閘門", "crash": "B 只在崩盤段生效",
           "vol": "C 波動目標", "dd": "D 回撤斷路器", "reentry": "E 停損後看影子回升才進場"}


def pct(x, sign=True):
    if x is None or x != x:
        return "—"
    return f"{x:+.1%}" if sign else f"{x:.1%}"


def num(x):
    return "—" if x is None or x != x else f"{x:.2f}"


def main():
    R = json.loads(RES.read_text(encoding="utf-8"))
    L = []
    w = L.append
    w("# DRAWDOWN_FIX.md — 回撤診斷與降回撤優化（先.一五二-1，Cowork 已定案，總司令 11/05「讓回測不要回那麼深」）")
    w("")
    w("> **性質：樣本內描述性最優化，不是判定。** 底層是 `REAUDIT_OPTIMIZED.md` 已經挑過一次參數的最優格，這裡又在同一段資料上再挑一次降回撤條件與槓桿——"
      "**兩層挑格子，數字一定偏樂觀**，只能拿來看「回撤是從哪裡來、哪種條件砍得到」，要靠紙上前向數據說話。資料只到 2024-12-31，holdout（2025+）未讀；零外部請求。非投資建議。")
    w("")
    w(f"程式：`research/drawdown_fix.py`（計算）、`research/drawdown_fix_report.py`（本檔）；產生：{R.get('_generated_at','—')}；"
      "曲線圖在本機 `research/data/drawdown_fix/F*.png`（`research/data/` 依 .gitignore 不進公開 repo，連結只在本機有效）。")
    w("")
    w("## 0. 方法（白話）")
    w("")
    w("1. **重建原版**：從 REAUDIT 存下的 1× 日權益快取（F12／F14／F17／F18）或原腳本的模擬器（F2／F10／F11 用 batch1 `simulate()`、F7 用台指期 `run()`）重算最優格，"
      "年化與 MDD 跟 REAUDIT 差距 <0.2 個百分點才往下做。")
    w("2. **回撤成因表**：原版曲線最深 5 段回撤，每段列起點／谷底／回到前高、深度、天數，並附同期大盤（台股個股家族用加權指數；F2／F10／F11 用 0050 含息淨值；F7 用台指期本身）"
      "漲跌、1× 底層同期跌幅與「放大倍數」（＝策略深度 ÷ 1× 底層深度，>1 代表槓桿放大）。歸因規則〔自行裁量〕：大盤同期跌 >8% 且與六大崩盤段重疊＝「跟著大盤崩」；大盤跌 <8%＝「策略自身」。")
    w("3. **降回撤條件**（曝險只用前一日以前的資訊）：A 大盤跌破 N 日均線→曝險乘 y（N∈60/120/200/250、y∈0/0.25/0.5）；"
      "B **只在崩盤段生效**：跌破 N 日均線**且**距 252 日高點跌超過 X 才降（N∈120/200/250、X∈10/15/20%、y∈0/0.25/0.5）；"
      "C 波動目標：近 k 日實現波動高於目標 t 就按比例降（k∈20/60、t∈10/15/20/30%，上限 1×）；"
      "D 回撤斷路器：**看 1× 底層影子曲線**（不看帳戶本身，避免第 9 關 absorbing state——帳戶降曝險後回不到前高就永遠解不開），影子回撤 ≥X 降到 y、回到 −Z 以內恢復。"
      "另加「不加條件、只調槓桿」當對照。每個版本再配原版帳戶停損或不停損。")
    w("4. **報酬不縮水（總司令 11/05 更正）**：每個版本把槓桿 L' 由低往高掃（個股家族 0.5～3.0 步 0.05；原生模擬器 1.0～3.0 步 0.1），"
      "取**第一個年化 ≥ 原版**的 L'，記下那時的 MDD／Calmar／Sharpe；全部版本中 MDD 最淺者＝降回撤版。L'>2 已超過台股融資實際上限，只當參考。")
    w("")
    w("## 1. 總表：原版 → 同年化降回撤版")
    w("")
    w("| 家族 | 期間 | 原版 L／年化／MDD／Calmar／Sharpe | 降回撤版條件 | 帳戶停損 | L' | 年化 | MDD | Calmar | Sharpe | MDD 改善 | 曲線 |")
    w("|---|---|---|---|---|---|---|---|---|---|---|---|")
    done, todo = [], []
    for fid in ORDER:
        x = R.get(fid)
        if not x or x.get("error") or "orig" not in x:
            todo.append(fid)
            continue
        done.append(fid)
        o, b = x["orig"], x.get("best")
        oc = f"{o['L']}×／{pct(o['cagr'])}／{pct(o['mdd'],False)}／{num(o['calmar'])}／{num(o['sharpe'])}"
        if b:
            s = b["same_cagr"]
            w(f"| {fid} {x['title']} | {x['period'][0]}～{x['period'][1]} | {oc} | {KIND_ZH[b['kind']]}：{b['desc']} | "
              f"{'—' if b['stop'] is None else pct(b['stop'],False)} | {s['L']} | {pct(s['cagr'])} | {pct(s['mdd'],False)} | {num(s['calmar'])} | {num(s['sharpe'])} | "
              f"{(s['mdd']-o['mdd'])*100:+.1f} 個百分點 | [png](data/drawdown_fix/{fid}.png) |")
        else:
            w(f"| {fid} {x['title']} | {x['period'][0]}～{x['period'][1]} | {oc} | 沒有任何版本在 L'≤3 達到原版年化 | — | — | — | — | — | — | — | — |")
    w("")
    w(f"已完成 {len(done)} 支：{'、'.join(done)}；**尚未做**：{'、'.join(todo) if todo else '無'}（見第 4 節）。")
    w("")
    w("## 2. 各家族：每一類條件的最好版本（同年化下）")
    w("")
    for fid in done:
        x = R[fid]
        o = x["orig"]
        w(f"### {fid} {x['title']}（原版 {pct(o['cagr'])}／{pct(o['mdd'],False)}；可達同年化的版本 {x['n_feasible']}／{x['n_variants']}）")
        w("")
        w("| 類別 | 最好的參數 | 帳戶停損 | 平均曝險係數 | 原槓桿下 年化／MDD／Calmar | 調回同年化 L' | MDD | Calmar | Sharpe |")
        w("|---|---|---|---|---|---|---|---|---|")
        for k in ("none", "ma", "crash", "vol", "dd", "reentry"):
            b = x["best_by_kind"].get(k)
            if not b:
                w(f"| {KIND_ZH[k]} | 沒有版本達到原版年化 | — | — | — | — | — | — | — |")
                continue
            a, s = b["atL0"], b["same_cagr"]
            trig = f"（觸發 {b['triggers']} 次）" if "triggers" in b else ""
            w(f"| {KIND_ZH[k]} | {b['desc']}{trig} | {'—' if b['stop'] is None else pct(b['stop'],False)} | {b['avg_expo_factor']:.2f} | "
              f"{pct(a['cagr'])}／{pct(a['mdd'],False)}／{num(a['calmar'])} | {s['L']} | {pct(s['mdd'],False)} | {num(s['calmar'])} | {num(s['sharpe'])} |")
        w("")
    stats_lev = [0, 0]
    w("## 3. 回撤成因表（原版曲線最深 5 段，依時間排序；圖上橘色陰影＝起點到谷底）")
    w("")
    for fid in done:
        x = R[fid]
        mk = x.get("market_proxy", "加權指數")
        w(f"### {fid} {x['title']}（大盤代理：{mk}）")
        w("")
        w(f"| # | 起點（前高） | 谷底 | 回到前高 | 深度 | 跌到谷底天數 | 總天數 | 同期大盤漲跌 | 同期大盤最大回撤 | 1× 底層同期 | 放大倍數 | 歸因 |")
        w("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for i, e in enumerate(x["episodes"], 1):
            cause = e["cause"]
            amp = e["amplify"]
            if e["base_1x_ret"] > -0.03 or (amp == amp and amp > 2.0):
                hit = x["orig"]["stop"] is not None
                cause = ("**槓桿＋帳戶停損造成**（1× 底層只小跌或上漲；停損出場後空手 21 日錯過反彈、再加融資利息）"
                         if hit else "**槓桿放大造成**（1× 底層只小跌）") + f"；原歸因：{e['cause']}"
                stats_lev[0] += 1
            stats_lev[1] += 1
            w(f"| {i} | {e['peak']} | {e['trough']} | {e['recovered']} | {pct(e['depth'],False)} | {e['days_to_trough']} | {e['days_total']} | "
              f"{pct(e['taiex_ret'])} | {pct(e['taiex_dd'],False)} | {pct(e['base_1x_ret'])} | {num(amp)} | {cause} |")
        w("")
    crash = sum(1 for fid in done for e in R[fid]["episodes"] if e["cause"].startswith("跟著大盤崩"))
    w(f"**成因統計**：{len(done)} 支 × 5 段＝{stats_lev[1]} 段裡，{crash} 段標「跟著大盤崩」，{stats_lev[0]} 段是**槓桿／帳戶停損自己造成**（1× 底層只小跌或上漲、放大倍數 >2）。")
    w("")
    w("## 3b. 主要發現（白話）")
    w("")
    w("1. **大盤濾網砍得到的回撤很有限**：同年化下 MDD 只淺 0.5～6 個百分點。原因是最深的幾段多半不是大盤崩盤造成——"
      "個股家族（F12／F16／F18）的深回撤常發生在大盤平穩或上漲時，是選股本身失靈，大盤條件看不到。")
    w("2. **帳戶停損本身會製造回撤**：原版最優格多帶 10～30% 帳戶停損＋停 21 天。槓桿 2～3 倍時，停損常在谷底出場、空手錯過反彈，"
      "1× 底層只跌幾 %（甚至上漲）的區間被放大成 −25%～−35%（F11 2020、F12 2020、F16 2020、F18 2023～24）。"
      "這種回撤不是市場給的，是規則給的。本輪試了 E 類「停損後改看 1× 影子曲線回升 0／3／5% 才進場」——**6 支都沒有變好、多數更差**"
      "（例：F17 −23.2%→−34.3%、F16 −30.7%→−36.9%），因為影子曲線回升時帳戶已錯過最陡的反彈、又得用更高槓桿補回年化。"
      "停損＋槓桿這個組合本身的回撤，用簡單的進場規則砍不掉。")
    w("3. **「只在崩盤段生效」的條件（B 類）在 5 支台股／0050 家族勝出**，符合總司令「只砍左尾、不砍平常」的方向，但改善幅度小；"
      "美股兩支與台指期是波動目標（C 類）勝出。")
    w("4. **交易次數少的家族（F11 5 筆）改善最多（−44.3%→−38.6%），也最不可信**：回撤來自 4～5 段單一事件，條件只是剛好避開其中一兩段。")
    w("")
    cp = HERE / "data" / "drawdown_fix" / "combo.json"
    if cp.exists():
        C = json.loads(cp.read_text(encoding="utf-8"))
        w("## 3c. 多策略組合（② 最後一項；`research/drawdown_fix_combo.py`）")
        w("")
        w(f"成員＝各家族**原版**日曲線（已含各自槓桿與停損）：{'、'.join(C['members'])}；共同期間 {C['period'][0]}～{C['period'][1]}（F18 只從 2020-10 起、太短，排除{'' if 'F10' in C['members'] else '；F10 曲線本輪未存到，未納入'}）。"
          "3～5 支所有組合 × 等權／反波動（60 日）每日再平衡，共 "
          f"{C['n_combos']} 個。〔自行裁量〕組合層不計再平衡成本、美股成員未換匯、組合加槓桿用台股融資 6.5% 近似——三者都讓數字偏樂觀。")
        w("")
        w("單支對照（同一段 2015～2024）：")
        w("")
        w("| 家族 | 年化 | MDD | Sharpe |")
        w("|---|---|---|---|")
        for f, v in C["single"].items():
            w(f"| {f} | {pct(v['cagr'])} | {pct(v['mdd'],False)} | {num(v['sharpe'])} |")
        w("")
        w("**組合再加槓桿調到目標年化時，MDD 最淺的前 3 名**（這才是「報酬不縮水、只砍回撤」的直接答案）：")
        w("")
        w("| 目標年化 | 組合 | 配重 | 平均相關 | 組合 L' | 調到目標後 MDD | 未加槓桿 年化／MDD |")
        w("|---|---|---|---|---|---|---|")
        for t, rows in C["levered_to_target"].items():
            for r in rows[:3]:
                w(f"| {float(t):.0%} | {r['members']} | {r['weight']} | {r['avg_corr']:.2f} | {r[f'L_{t}']} | {pct(r[f'mdd_{t}'],False)} | {pct(r['cagr'])}／{pct(r['mdd'],False)} |")
        w("")
        w("讀法：同一段期間，單支要拿到年化 ~25% 得承受 −30% 左右（F12 2×）到 −44%（F11 3×）的回撤；"
          "把相關性低的 3～4 支混在一起再略加槓桿，同樣年化的回撤約 −17%～−20%。**這是本輪唯一明顯的降回撤來源**，"
          "但成員本身都是樣本內挑出來的最優格（兩層挑選），期間只有 10 年，前向一定打折。")
        w("")
    w("## 4. 尚未做（照實寫，下一輪續）")
    w("")
    w("- **個股層歸因**（前 3 檔貢獻、產業集中、跳空／跌停賣不掉、換股太慢）：要從引擎 trades 重跑最優格（F12／F14／F18 每格約數分鐘），本輪未做。")
    w("- **個股停損＋跳空處理、產業上限**：要重跑引擎（新格），下一輪做；**台指期空單避險**：可用 F7 的 TX 連續合約報酬當避險腿，下一輪做（含放空腿的數字要附資料缺陷但書；期貨空單無借券問題）。")
    if cp.exists() and "F10" not in C["members"]:
        w("- **F10 進組合**：F10 日曲線本輪沒存到，下一輪跑 `python research/drawdown_fix.py F10` 後重跑 `drawdown_fix_combo.py` 與本報告。")
    w("- **先.一五〇-2 恐慌 PQ**：原版年化 +2.1%／MDD −8.3%，回撤本來就淺，等其他項做完再套同一套。")
    w("- **上紙上（第 ④ 步）**：前向模擬上限 14／14 已滿（CLAUDE.md 零之二⑤），不新增登記；全部家族做完後把最好的降回撤版寫進 `research/FORWARD_CANDIDATES.md` 候選清單。")
    w("")
    w("## 5. 讀法與但書")
    w("")
    w("- 降回撤版年化「≥ 原版」是在同一段資料上挑出來的，前向一定會打折；MDD 改善幅度小（幾個百分點）的，大多落在雜訊範圍，不要當成真的有改善。")
    w("- 交易次數很少的家族（F11 5 筆、F10 11 筆）回撤來自少數幾段事件，條件只是剛好避開那幾段，參數高原很窄，最容易過擬合。")
    w("- F15／F16 為美股：存活者偏誤未完全修正：已下市股約 97%（抽樣 55／57）無價格來源。")
    w("- 本研究不登記試驗（描述性最優化，比照 REAUDIT 與先.一五〇-2 做法），心跳寫 `research/PROGRESS_HEARTBEAT.jsonl`。")
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"寫入 {OUT}（完成 {len(done)}，待做 {todo}）")


if __name__ == "__main__":
    main()
