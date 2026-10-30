# -*- coding: utf-8 -*-
"""研究成績單資料檔（2026-10-13 總司令【先.八十二】9＋【先.八十三】5）。

把試驗帳本、墓園驗屍與前進式（樣本外）對照整理成 App「研究成績單」頁要用的一份小檔 data/research_scorecard.json：
  ① 測過幾種方法：data/trials_index.json（試驗帳本，含重號說明）的總數、判定分類、各軌數量
  ② 各自為什麼死：research/GRAVEYARD_AUTOPSY.md（先.八十三-1）逐條表＋A／B／C 統計
  ③ 有沒有策略贏 0050：data/strategy_curves.json 每條線「同期 0050」對照（上線後的真實走勢＝樣本外）
結論句由資料算出，不寫死：只有「樣本外 ≥ MIN_DAYS 個交易日且累積報酬高於同期 0050」才算贏；
天數不足的領先照實標「天數不足，不能判斷」。零網路請求。
用法：python scripts/build_research_scorecard.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
TW = timezone(timedelta(hours=8))
OUT = ROOT / "data" / "research_scorecard.json"
MIN_DAYS = 60  # 樣本外至少 60 個交易日才拿來判斷「贏不贏 0050」（約一季）
CLASS_LABEL = {"A": "流程錯（程式、資料、成本、標籤出錯）", "B": "資料不足（拿不到、樣本太短、檢定力不夠）",
               "C": "流程對但沒有優勢"}


def _read(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def verdict_bucket(v: str | None) -> str:
    s = str(v or "")
    if s.startswith("VIOLATES_SURVIVAL"):
        return "違反天條一（最大回撤超過 50%）"
    if s.startswith("FAIL"):
        return "未通過"
    if s.startswith("CHEAP_PASS"):
        return "初篩通過（未完成全部關卡）"
    if s.startswith("PASS"):
        return "通過判準"
    if s.startswith("EXPERIMENTAL"):
        return "實驗中"
    return "其他（描述性研究、資料不可用、無法重現等）"


def trials_block() -> dict:
    d = _read(ROOT / "data" / "trials_index.json")
    rows = d.get("rows") or []
    return {"count": d.get("count"), "count_rule": d.get("count_rule"),
            "by_verdict": Counter(verdict_bucket(r.get("verdict")) for r in rows).most_common(),
            "by_track": Counter(str(r.get("track") or "其他") for r in rows).most_common(),
            "passed": [{"id": r.get("id"), "name": r.get("name"), "verdict": str(r.get("verdict"))[:60]}
                       for r in rows if verdict_bucket(r.get("verdict")) == "通過判準"]}


def autopsy_block() -> dict:
    txt = (ROOT / "research" / "GRAVEYARD_AUTOPSY.md").read_text(encoding="utf-8")
    js = json.loads(re.findall(r"```json\n(.*?)```", txt, re.S)[-1])
    sec = txt.split("## 3.", 1)[1].split("\n## 4.", 1)[0]
    rows = []
    for line in sec.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 6 and cells[0].isdigit():
            cls = cells[3].replace("（邊界）", "").strip()[:1]
            rows.append({"name": cells[1], "date": cells[2], "class": cls, "borderline": "邊界" in cells[3],
                         "why": cells[4]})
    return {"total": js.get("total"), "counts": js.get("counts"), "borderline": js.get("borderline"),
            "labels": CLASS_LABEL, "rows": rows, "source": "research/GRAVEYARD_AUTOPSY.md（先.八十三-1）"}


def oos_block() -> dict:
    d = _read(ROOT / "data" / "strategy_curves.json")
    lines = []
    for l in d.get("lines") or []:
        m = l.get("metrics") or {}
        if not m.get("days"):
            lines.append({"id": l.get("id"), "label": l.get("label"), "group": l.get("group"), "status": l.get("status"),
                          "days": 0, "note": "尚未開始或沒有資料", "start": l.get("start_date"),
                          "design_note": l.get("design_note"), "candidacy": l.get("candidacy")})
            continue
        days, gap = m.get("days"), m.get("cum_gap_pp")
        if gap is None:  # 先.一三五-1df：差距讀不到只標該列，不讓整段 oos 變 error
            judge = "缺資料（讀不到跟 0050 的差距）"
        else:
            judge = ("贏 0050" if gap > 0 else "輸 0050") if days >= MIN_DAYS else (
                f"天數不足（{days} 天 < {MIN_DAYS}），{'暫時領先' if gap > 0 else '暫時落後'}，不能判斷")
        lines.append({"id": l.get("id"), "label": l.get("label"), "group": l.get("group"), "status": l.get("status"),
                      "start": l.get("start_date"), "as_of": l.get("as_of"), "days": days,
                      "ret_pct": m.get("cum_pct"), "bench_pct": m.get("bench_cum_pct"), "gap_pp": gap,
                      "mdd_pct": m.get("mdd_pct"), "bench_mdd_pct": m.get("bench_mdd_pct"), "judge": judge,
                      "design_note": l.get("design_note"), "candidacy": l.get("candidacy")})
    # 先.一三五-1df：結論句依實際勝負數產生（全落後／部分領先／全領先），不寫死「全部落後」
    mature = [x for x in lines if x.get("days", 0) >= MIN_DAYS]
    winners = [x for x in mature if x.get("gap_pp") is not None and x["gap_pp"] > 0]
    losers = [x for x in mature if x.get("gap_pp") is not None and x["gap_pp"] <= 0]
    missing = len(mature) - len(winners) - len(losers)
    longest = max((x.get("days", 0) for x in lines), default=0)
    tail = f"（另有 {missing} 條缺資料）" if missing else ""
    if winners and not losers:
        concl = (f"已滿 {MIN_DAYS} 個交易日的 {len(winners)} 條全部領先同期 0050：" + "、".join(x["label"] for x in winners)
                 + tail + "。")
    elif winners:
        concl = (f"已滿 {MIN_DAYS} 個交易日的 {len(winners) + len(losers)} 條中 {len(winners)} 條領先、{len(losers)} 條落後同期 0050；"
                 "領先的是：" + "、".join(x["label"] for x in winners) + tail + "。")
    elif losers:
        concl = (f"目前沒有任何策略在樣本外贏過 0050：已滿 {MIN_DAYS} 個交易日的 {len(losers)} 條全部落後同期 0050"
                 f"（最長 {longest} 個交易日）" + tail + "。")
    else:
        concl = (f"目前沒有任何策略在樣本外贏過 0050。最長的樣本外紀錄只有 {longest} 個交易日"
                 f"（要 ≥{MIN_DAYS} 天才拿來判斷），還沒有可判輸贏的選股榜" + tail + "。")
    return {"min_days": MIN_DAYS, "lines": lines, "winners": [x["label"] for x in winners], "conclusion": concl,
            "source": "data/strategy_curves.json（上線後的真實走勢，與同期 0050 還原含息比較）"}


# 先.九十一-1／-5-1（2026-10-14 總司令裁示）：研究成績單「四、研究說明」——已知現象與不做的路線，照實寫原因
NOTES = [
    {"title": "賣波動（模擬 F）：學界已知現象、只是研究",
     "body": "試驗 #444：2002–2014 台指選擇權的隱含波動度平均比事後實際波動高約 3 個百分點，每月賣一組價平跨式扣成本後月均約 +0.38%，"
             "但年化只有約 4.6%、最差一個月 −16%、最大回撤 37%，試驗間比較數字（DSR）也算不出來。"
             "所以不提請真錢（每組名目約數百萬元，選擇權真錢需另案核准）；2026-11 起只做紙上追蹤，不倒填。"},
    {"title": "權證不做（賺波動溢價這條路）",
     "body": "台股權證散戶只能買、不能發行，買權證就是站在「付波動溢價」的一方，跟模擬 F 的賣方方向相反。"
             "所以權證不能拿來賺波動溢價。權證只當買方工具另外研究（先.九十二 權證研究線，先查資料、不登記試驗）。"},
]


def main() -> int:
    doc = {"meta": {"generated_at": datetime.now(TW).isoformat(timespec="seconds"),
                    "source": "scripts/build_research_scorecard.py：data/trials_index.json＋research/GRAVEYARD_AUTOPSY.md＋data/strategy_curves.json",
                    "note": "研究紀錄整理，非投資建議"}}
    doc["notes"] = NOTES
    for k, fn in (("trials", trials_block), ("autopsy", autopsy_block), ("oos", oos_block)):
        try:
            doc[k] = fn()
        except Exception as e:  # noqa: BLE001 — 單一區塊失敗只標錯誤，不擋其他區塊（App 照樣顯示其他段）
            doc[k] = {"error": f"{type(e).__name__}: {e}"[:200]}
    if all("error" in doc[k] for k in ("trials", "autopsy", "oos")):  # 先.一三五-1cu：三段全失敗不覆寫上一版
        print("[warn] 三個輸入全部讀不到：" + "；".join(doc[k]["error"] for k in ("trials", "autopsy", "oos"))
              + "，research_scorecard.json 維持原狀")
        return 0
    tmp =OUT.with_name(OUT.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(OUT)
    a = doc.get("autopsy") or {}
    print(f"research_scorecard：試驗 {(doc.get('trials') or {}).get('count')} 筆、墓園 {a.get('total')} 列 {a.get('counts')}、"
          f"{OUT.stat().st_size / 1024:.0f} KB；{(doc.get('oos') or {}).get('conclusion')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
