# -*- coding: utf-8 -*-
"""先.一五五-3 ①：墓園重審第二批清單——把 TRIALS_LEDGER 依機制家族分組，扣掉第一批已做的族。

只讀 `research/TRIALS_LEDGER.md`（表格列）＋`research/TRIALS_REGISTRY.jsonl`（補 name／design 文字），
零外部請求、不寫任何帳本（帳本只能經 register_trial() 寫）。輸出：
  research/data/reaudit_batch3_inventory.json（每族：試驗編號、代表名稱、可轉成哪種交易規則、判定分佈）
分族規則〔自行裁量，自動、可重跑、可推翻〕：
  1. 整列文字裡第一個因子識別字 `f_xxx`（同名＝同族；f_us_ 前綴視為美股另一族）；
  2. 否則第一個 `xxx.py` 腳本名（去掉 _v1／_gate／_backtest 等尾碼）；
  3. 否則 `HYPOTHESIS_QUEUE #NN` 假說編號；
  4. 都沒有 → 假說名稱欄前 18 字當族名（單列一族，人工下一批再併）。
可轉成交易規則的分類（照條目②）：因子→前 N 檔等權月換股；regime／閘門／擇時→0050 曝險；
事件→事件後固定持有；描述性／校準／稽核重跑／量尺驗證→「非策略，跳過」。
用法：python research/reaudit_batch3_inventory.py
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
LEDGER = HERE / "TRIALS_LEDGER.md"
REG = HERE / "TRIALS_REGISTRY.jsonl"
OUT = HERE / "data" / "reaudit_batch3_inventory.json"

# 第一批（先.一五〇-1，REAUDIT_OPTIMIZED.md 第 1 節表格）已涵蓋或已判跳過的試驗編號
BATCH1_IDS = {64, 151, 128, 144, 418, 420, 425, 424, 426, 428, 133, 136, 137, 384, 171, 282, 430, 413, 16, 17,
              414, 243, 416, 247, 248, 483, 253, 254, 255, 256, 257, 258, 259, 260, 261, 349, 249, 11, 393, 283,
              244, 250, 251, 252, 445, 446, 232, 383}
# 第一批家族的關鍵字（整族任一列文字含這些字＝第一批已涵蓋；照 REAUDIT_OPTIMIZED.md 第 1 節 F1～F18 對照）
BATCH1_KEYWORDS = ("bb90", "Bb-90", "short_sale_utilization", "sector_flow", "credit_spread", "trend_leverage",
                   "trend_scale", "roe_stability", "realized_vol", "breadth", "ml_pricevol", "margin_debt_level",
                   "margin_debt_market", "weinstein", "core_tilt", "odd_lot", "f_us_low_vol", "f_us_value_bm",
                   "tx_200ma", "fut_200ma")
# 關鍵字誤判、人工確認不是第一批家族的（台股 f_low_vol ≠ F15 美股低波動；#28 廣度背離 ≠ F10 廣度 regime 等）
NOT_BATCH1 = {"f_low_vol", "f_inst_streak_days", "vol_targeting", "breadth_divergence_sanity"}
# 第一批另含先.一五〇-2 恐慌 PQ（PQ 列），其試驗不在帳本（紙上優化軌不登記）

SKIP_PAT = re.compile(r"描述性|校準|探針|稽核重跑|重跑：|吻合度|量尺|資料品質|覆蓋率|sanity|CALIBRATION|PENDING_CALIBRATION")
EVENT_PAT = re.compile(r"事件|CAR|公告|除權|減資|增資|法說|財報公布|PEAD")
REGIME_PAT = re.compile(r"regime|閘門|擇時|曝險|趨勢|均線|MA|200MA|波動度|台指期|TX|0050|VIX|殖利率曲線|利差")
FACTOR_PAT = re.compile(r"因子|IC|f_[a-z]")
SUFFIX = re.compile(r"(_v\d+|_gate|_backtest|_portfolio|_test|_probe|_tracker|_run|_cheap)+$")


def ledger_rows() -> dict[int, str]:
    rows: dict[int, str] = {}
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| *(\d+) *\|", line)
        if m:
            i = int(m.group(1))
            rows[i] = rows.get(i, "") + " " + line
    if REG.exists():
        for line in REG.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
                i = int(d["id"])
            except Exception as e:  # 單列壞掉只略過
                print(f"[warn] REGISTRY 列解析失敗：{e}")
                continue
            rows[i] = rows.get(i, "") + " " + " ".join(str(d.get(k, "")) for k in ("name", "design", "verdict"))
    return rows


def family_key(text: str) -> str:
    m = re.search(r"\bf_[a-z0-9_]+", text)
    if m:
        return m.group(0).rstrip("_")
    m = re.search(r"([a-z][a-z0-9_]+)\.py", text)
    if m and m.group(1) not in ("trial_registry", "costs", "engine", "pit", "adjust", "selection_bias_ledger"):
        return SUFFIX.sub("", m.group(1))
    m = re.search(r"#\s?(\d{1,3})(?!\d)", text.split("|", 5)[-1] if "|" in text else text)
    if m:
        return f"HQ#{m.group(1)}"
    cols = [c.strip() for c in text.split("|")]
    name = cols[4] if len(cols) > 4 else text
    return "名稱:" + re.sub(r"[`*（(].*$", "", name)[:18]


def kind(text: str) -> str:
    if SKIP_PAT.search(text):
        return "非策略，跳過"
    if EVENT_PAT.search(text):
        return "事件→事件後固定持有"
    if REGIME_PAT.search(text) and not re.search(r"\bf_", text):
        return "regime→0050 曝險"
    if FACTOR_PAT.search(text) or "策略" in text:
        return "因子→前 N 檔等權月換股"
    return "待人工判斷"


def verdict(text: str) -> str:
    for v in ("VIOLATES_SURVIVAL", "CHEAP_PASS", "PASS", "FAIL", "INCONCLUSIVE"):
        if v in text:
            return v
    return "其他"


def main() -> int:
    rows = ledger_rows()
    fam: dict[str, dict] = {}
    for i, t in sorted(rows.items()):
        k = family_key(t)
        f = fam.setdefault(k, {"family": k, "ids": [], "kinds": collections.Counter(), "verdicts": collections.Counter(),
                               "sample": ""})
        f["ids"].append(i)
        f["kinds"][kind(t)] += 1
        f["verdicts"][verdict(t)] += 1
        if not f["sample"]:
            cols = [c.strip() for c in t.split("|")]
            f["sample"] = (cols[4] if len(cols) > 4 and cols[4] else t.strip())[:80]
    out = []
    for f in fam.values():
        done = sorted(set(f["ids"]) & BATCH1_IDS)
        # 只比對族名＋各列「假說名稱」欄（第 4 欄），不比備註——備註常順帶提到別的家族，會誤吞
        txt = f["family"] + " " + " ".join((rows[i].split("|")[4] if rows[i].count("|") > 4 else rows[i][:120]) for i in f["ids"])
        hit = [k for k in BATCH1_KEYWORDS if k.lower() in txt.lower()]
        if hit and not done and f["family"] not in NOT_BATCH1:
            done = [f"關鍵字:{hit[0]}"]
        out.append({"family": f["family"], "n_trials": len(f["ids"]), "ids": f["ids"],
                    "batch1_overlap": done, "status": "第一批已做" if done else "第二批待做",
                    "kind": f["kinds"].most_common(1)[0][0], "verdicts": dict(f["verdicts"]), "sample": f["sample"]})
    out.sort(key=lambda d: (d["status"] != "第二批待做", d["kind"] == "非策略，跳過", -d["n_trials"], d["family"]))
    meta = {"n_trials": len(rows), "n_families": len(out),
            "n_batch1": sum(d["status"] == "第一批已做" for d in out),
            "n_todo": sum(d["status"] == "第二批待做" and d["kind"] != "非策略，跳過" for d in out),
            "n_skip": sum(d["status"] == "第二批待做" and d["kind"] == "非策略，跳過" for d in out),
            "kind_counts": dict(collections.Counter(d["kind"] for d in out if d["status"] == "第二批待做")),
            "network_requests": 0}
    OUT.write_text(json.dumps({"meta": meta, "families": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))
    write_md(meta, out)
    return 0


# 第二批第 1 個 10 族批次〔自行裁量〕：曾經 PASS／CHEAP_PASS、可轉成可交易規則、且本機台股價格＋財報快取接得上 2025 起
FIRST10 = ["f_eps_surprise", "f_revenue_surprise", "f_eps_growth", "f_value_pe", "f_value_pb", "f_low_vol",
           "f_rel_strength", "f_52w_high_prox", "f_dividend_yield_ttm", "f_gross_profitability"]
MD = HERE / "REAUDIT_OPTIMIZED.md"
B, E = "<!-- BATCH3-LIST-BEGIN -->", "<!-- BATCH3-LIST-END -->"


def write_md(meta: dict, fams: list[dict]) -> None:
    v = lambda d: "、".join(f"{k}×{n}" for k, n in d.items())
    L = [B, "## 4. 第二批清單（先.一五五-3 ①②，`research/reaudit_batch3_inventory.py` 自動產生，零請求、只讀帳本）", "",
         f"TRIALS_LEDGER＋TRIALS_REGISTRY 共 **{meta['n_trials']}** 筆試驗（編號 1～{max(i for f in fams for i in f['ids'])}），"
         f"自動分成 **{meta['n_families']}** 族：第一批已涵蓋 {meta['n_batch1']} 族；第二批待做 **{meta['n_todo']}** 族；"
         f"判「非策略，跳過」{meta['n_skip']} 族。",
         "",
         "分族與分類規則〔自行裁量，自動、可重跑、可推翻〕：同一個因子名 `f_xxx`／同一支腳本／同一個 HYPOTHESIS_QUEUE 假說編號＝同一族；"
         "都抓不到的單列成族。分類：因子→前 N 檔等權月換股；regime／閘門／擇時→0050 曝險；事件→事件後固定持有；"
         "描述性／校準／稽核重跑／量尺驗證→非策略跳過。**自動分類有誤判**（例如事件與因子的界線、同機制不同名），"
         "每一批開做前人工複核該批 10 族，併族或改分類就改腳本裡的對照表再重跑，不手改本節。",
         "",
         "**第 1 批（10 族，下一輪起做）**〔自行裁量：曾 PASS／CHEAP_PASS、可轉成交易規則、本機台股價格＋財報快取接得上 2025 起〕："
         + "、".join(f"`{x}`" for x in FIRST10) + "。做法照條目③：全部可得歷史（含 2025 起）掃參數、持有期、止盈止損、槓桿 1×／1.5×／2×／3×，"
         "記最好一組併入總表重排。",
         "",
         "| 狀態 | 族 | 試驗數 | 編號（前 8） | 轉成什麼規則 | 當時判定 | 代表名稱 |", "|---|---|---|---|---|---|---|"]
    for f in fams:
        st = f["status"] if f["status"] == "第一批已做" else ("跳過" if f["kind"] == "非策略，跳過" else "待做")
        if f["family"] in FIRST10 and st == "待做":
            st = "**第 1 批**"
        nm = f["sample"].replace("|", "／").replace("`", "")[:50]
        L.append(f"| {st} | {f['family'].replace('|', '／')} | {f['n_trials']} | {','.join(map(str, f['ids'][:8]))} | {f['kind']} | {v(f['verdicts'])} | {nm} |")
    L.append(E)
    txt = MD.read_text(encoding="utf-8")
    blk = "\n".join(L)
    if B in txt and E in txt:
        txt = txt[:txt.index(B)] + blk + txt[txt.index(E) + len(E):]
    else:
        txt = txt.rstrip("\n") + "\n\n" + blk + "\n"
    MD.write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
