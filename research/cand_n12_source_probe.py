"""先.一三五-1q 候選 N12 前置：可轉債轉換價向下重設公告的來源可得性（零請求）。

只讀本機檔案、只數標題，不送任何網路請求、不讀價格、不算報酬、不登記試驗。
- 重大訊息歸檔：research/data/mops_events_archive.jsonl（先.一三五-1d，TWSE／TPEx 重大訊息 openapi 的每日累積，非 MOPS 爬取）
- TPEx swagger：research/data/raw/tpex_exright_probe/swagger.bin（2026-10-23 已存）
- TWSE openapi：本機沒有存 swagger，只列 repo 程式碼已用到的端點
輸出：research/data/cand_n12_source_probe.json
"""
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "research/data/mops_events_archive.jsonl"
SWAGGER = ROOT / "research/data/raw/tpex_exright_probe/swagger.bin"
OUT = ROOT / "research/data/cand_n12_source_probe.json"

CB_WORDS = re.compile(r"轉換價|轉換公司債|可轉換")
DOWN_RESET = re.compile(r"重設|向下")
ANTI_DILUTION = re.compile(r"除權|除息|配股|配息|現金增資|增資|反稀釋|無償配發")
ADJUST = re.compile(r"轉換價[格]?.{0,4}調整|調整.{0,30}轉換價")
NEW_ISSUE_PRICE = re.compile(r"轉換價格(及|與)?(轉換)?溢價率|完成訂價")


def classify(title: str) -> str:
    title = re.sub(r"\s+", "", title)
    if DOWN_RESET.search(title) and "股息率" not in title:
        return "向下重設"
    if ADJUST.search(title):
        return "反稀釋調整" if ANTI_DILUTION.search(title) else "其他_轉換價調整未標原因"
    if NEW_ISSUE_PRICE.search(title):
        return "其他_新發行訂價"
    return "其他"


def main() -> None:
    rows = [json.loads(l) for l in ARCHIVE.open(encoding="utf-8") if l.strip()]
    dates = sorted(r["date"] for r in rows)
    hits = []
    seen = set()
    for r in rows:
        t = r["title"]
        if not (re.search(r"轉換價|重設", t) or (CB_WORDS.search(t) and "調整" in t)):
            continue
        key = (r["code"], r["date"], t)
        dup = key in seen
        seen.add(key)
        hits.append({"date": r["date"], "code": r["code"], "source": r["source"],
                     "title": t, "class": classify(t), "duplicate": dup})
    uniq = [h for h in hits if not h["duplicate"]]
    by_class = Counter(h["class"] for h in uniq)

    sw = json.loads(SWAGGER.read_text(encoding="utf-8"))
    cb_eps = []
    for p, v in sw["paths"].items():
        for o in v.values():
            s = f"{o.get('summary', '')} {' '.join(o.get('tags', []))}"
            if re.search(r"轉換|可轉|轉\(交\)換", s):
                cb_eps.append({"path": p, "summary": o.get("summary", "")})
    issbd5 = list(sw["paths"]["/bond_ISSBD5_data"].values())[0]
    sch = list(issbd5["responses"]["200"]["content"].values())[0]["schema"]
    if "$ref" in sch:
        sch = sw["components"]["schemas"][sch["$ref"].split("/")[-1]]
    if sch.get("type") == "array":
        it = sch["items"]
        sch = sw["components"]["schemas"][it["$ref"].split("/")[-1]] if "$ref" in it else it
    conv_fields = {k: v.get("description", "") for k, v in sch.get("properties", {}).items()
                   if "Conversion" in k or "轉換" in v.get("description", "")}

    try:
        g = subprocess.run(["git", "grep", "-ohE", r"openapi\.twse\.com\.tw/v1/[A-Za-z0-9_/]+", "--", "*.py"],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60)
        twse_eps = sorted(set(g.stdout.split()))
    except Exception as e:  # 守門員只降級成警告
        print(f"警告：列 TWSE 端點失敗：{e}")
        twse_eps = []
    twse_cb = [e for e in twse_eps if re.search(r"bond|cb|conv", e, re.I)]

    span_days = (datetime.fromisoformat(dates[-1]) - datetime.fromisoformat(dates[0])).days + 1
    n_down = by_class.get("向下重設", 0)
    out = {
        "item": "先.一三五-1q",
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "network_requests": 0,
        "archive": {"path": str(ARCHIVE.relative_to(ROOT)).replace("\\", "/"), "rows": len(rows),
                    "date_min": dates[0], "date_max": dates[-1], "span_days": span_days},
        "title_hits": len(hits), "title_hits_unique": len(uniq),
        "by_class": dict(by_class),
        "monthly_avg_down_reset": round(n_down / span_days * 30.4, 2),
        "monthly_avg_adjust_unlabeled": round(by_class.get("其他_轉換價調整未標原因", 0) / span_days * 30.4, 2),
        "hits": hits,
        "tpex_swagger_cb_endpoints": cb_eps,
        "tpex_ISSBD5_conversion_fields": conv_fields,
        "twse_openapi_endpoints_used_in_repo": twse_eps,
        "twse_openapi_cb_endpoints_in_repo": twse_cb,
        "verdict": ("前向可得（重大訊息歸檔）" if n_down > 0
                    else "歸檔抓不到，需另查 TPEx 可轉債開放資料"),
        "notes": [
            "重大訊息標題只寫「轉換價格調整」不寫原因，向下重設與除權息反稀釋調整在標題層級分不開；內文不在歸檔裡。",
            "TPEx swagger 的轉(交)換債發行資料（bond_ISSBD5_data）只有「發行時轉換價格」，沒有現行轉換價或重設紀錄。",
            "TWSE openapi 本機無 swagger 存檔，只列 repo 已用端點；需送請求的三來源查證另案。",
            "MOPS robots 全站 Disallow，不抓。",
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("archive", "title_hits_unique", "by_class", "verdict")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
