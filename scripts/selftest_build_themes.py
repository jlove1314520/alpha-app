#!/usr/bin/env python3
"""先.一三五-1el：題材庫重建（scripts/build_themes.py，news_events.yml 每班）合成自測。

零外部請求：data／seed／輸出路徑全部換到暫存目錄，news_matcher 換成假模組（只認公司名「台積電」→ 2330）。
測：句型＋公司名稱反向排除、同文轉載只算一個來源、內文 C 級、append-only 沿用既有 effective_from、
新成員用新聞發布日、讀不到輸入／既有檔就不覆寫、寫出合法 JSON 且不留 .tmp。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
fails: list[str] = []
total = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global total
    total += 1
    print(f"  {'OK ' if ok else 'FAIL'} {name}{'' if ok else '　' + detail}")
    if not ok:
        fails.append(name)


fake_nm = types.ModuleType("news_matcher")
fake_nm.load_company_names = lambda: ({"台積電": "2330", "日月光": "3711"}, set())
fake_nm.load_active_codes = lambda: {"2330", "3711"}


def _match(title, body, name2code, active):
    txt = (title or "") + (body or "")
    return {"codes": [c for n, c in name2code.items() if n in txt and c in active]}


fake_nm.match_article = _match
sys.modules["news_matcher"] = fake_nm

spec = importlib.util.spec_from_file_location("bt", ROOT / "scripts" / "build_themes.py")
bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bt)

# ── 純函式 ─────────────────────────────────────────────
print("[純函式]")
check("轉載去括號後同一來源鍵",
      bt._source_key("台積電 擴產CoWoS（專家：輝達）") == bt._source_key("台積電擴產CoWoS 專家：輝達"))
check("內容不同來源鍵不同", bt._source_key("A公司擴產CoWoS") != bt._source_key("B公司擴產CoWoS"))
check("關鍵詞只在公司名稱裡 → 不算", not bt.kw_outside_company_name("代子公司上海易統食品貿易有限公司公告租賃", "食品"))
check("關鍵詞在名稱外出現過一次 → 算", bt.kw_outside_company_name("易統食品貿易有限公司擴大食品產線", "食品"))
PATS = ["打入{theme}供應鏈", "{theme}擴產"]
check("句型命中", bt.evidence_keyword("台積電CoWoS擴產", ["CoWoS"], PATS) == ("CoWoS", "CoWoS擴產"))
check("只有共現沒有句型 → 不採", bt.evidence_keyword("台積電與CoWoS", ["CoWoS"], PATS) == (None, None))
check("_earliest_pub 取最早、取不到回 fallback",
      bt._earliest_pub([{"url": "a"}, {"url": "b"}], {"a": "2026-09-08", "b": "2026-09-06"}, "X") == "2026-09-06"
      and bt._earliest_pub([{"url": "z"}], {}, "X") == "X")


def setup(tmp: Path) -> None:
    d = tmp / "data"
    (d / "seed").mkdir(parents=True)
    bt.D, bt.SEED, bt.KWMAP, bt.OUT = d, d / "seed" / "seed_themes_validated.json", d / "seed" / "theme_keywords.json", d / "themes.json"
    bt.ROOT = tmp
    w = lambda p, o: p.write_text(json.dumps(o, ensure_ascii=False), encoding="utf-8")
    w(bt.SEED, {"themes": [
        {"id": "adv_package", "name": "先進封裝", "kw": ["CoWoS"], "members": ["2330", "3711"]},
        {"id": "food", "name": "食品", "kw": ["食品"], "members": ["2330"]},
    ]})
    w(bt.KWMAP, {"themes": {}, "sentence_patterns": {"patterns": PATS}})
    w(d / "news.json", {"news": [
        {"title": "台積電CoWoS擴產", "url": "https://a.com/1", "published": "2026-10-01T08:00"},
        {"title": "台積電 （CoWoS擴產）", "url": "https://b.com/1", "published": "2026-10-02T08:00"},
        {"title": "台積電代子公司台積食品有限公司公告", "url": "https://c.com/1", "published": "2026-10-03"},
    ]})
    w(d / "events.json", {"events": []})
    w(d / "news_evidence.json", {"evidence": [
        {"url": "https://x.com/9", "source": "x", "date": "2026-09-20",
         "quotes": [{"theme_id": "adv_package", "codes": ["3711"], "pattern": "打入CoWoS供應鏈",
                     "matched": "CoWoS", "quote": "日月光打入CoWoS供應鏈"}]},
    ]})
    w(d / "news_urls.json", {"urls": [{"url": "https://a.com/1", "published": "2026-10-01"},
                                      {"url": "https://b.com/1", "published": "2026-10-02"},
                                      {"url": "https://x.com/9", "published": "2026-09-20"}]})


with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    setup(tmp)
    print("[第一次建檔]")
    rc = bt.main()
    doc = json.loads(bt.OUT.read_text(encoding="utf-8"))
    ms = {(m["code"], m["theme_id"]): m for m in doc["memberships"]}
    check("exit 0", rc == 0, str(rc))
    check("不留 .tmp", not (bt.D / "themes.json.tmp").exists())
    check("2330 先進封裝＝C 級", ("2330", "adv_package") in ms and ms[("2330", "adv_package")]["level"] == "C")
    check("同文轉載只算一個來源 → 低信心", ms.get(("2330", "adv_package"), {}).get("confidence") == "low",
          str(ms.get(("2330", "adv_package"), {}).get("confidence")))
    check("新成員 effective_from＝最早新聞發布日",
          ms.get(("2330", "adv_package"), {}).get("effective_from") == "2026-10-01")
    check("內文 C 級（3711）用發布日 2026-09-20", ms.get(("3711", "adv_package"), {}).get("effective_from") == "2026-09-20")
    check("食品只在子公司名裡 → 不入選", ("2330", "food") not in ms)
    check("meta 計數一致", doc["meta"]["members_C"] == len(doc["memberships"]) == 2)

    print("[append-only]")
    doc["memberships"][0]["effective_from"] = "2026-01-01"
    k0 = (doc["memberships"][0]["code"], doc["memberships"][0]["theme_id"])
    bt.OUT.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    bt.main()
    ms2 = {(m["code"], m["theme_id"]): m for m in json.loads(bt.OUT.read_text(encoding="utf-8"))["memberships"]}
    check("既有成員沿用舊 effective_from", ms2[k0]["effective_from"] == "2026-01-01"
          and ms2[k0]["effective_from_basis"] == "沿用既有值")

    print("[讀不到就不覆寫]")
    good = bt.OUT.read_bytes()
    for name in ("news.json", "events.json", "news_evidence.json"):
        p = bt.D / name
        keep = p.read_bytes()
        p.write_text("{壞", encoding="utf-8")
        rc = bt.main()
        check(f"{name} 壞檔 → exit 1、themes.json 位元組不變", rc == 1 and bt.OUT.read_bytes() == good, str(rc))
        p.unlink()
        rc = bt.main()
        check(f"{name} 不存在 → exit 1、themes.json 位元組不變", rc == 1 and bt.OUT.read_bytes() == good, str(rc))
        p.write_bytes(keep)
    bt.OUT.write_text("{壞", encoding="utf-8")
    rc = bt.main()
    check("既有 themes.json 壞檔 → exit 1、不覆寫", rc == 1 and bt.OUT.read_text(encoding="utf-8") == "{壞", str(rc))
    bt.OUT.unlink()
    rc = bt.main()
    check("themes.json 不存在（首次）→ 照常建檔", rc == 0 and json.loads(bt.OUT.read_text(encoding="utf-8"))["memberships"])

print(f"\n{total - len(fails)} 過 {len(fails)} 失敗")
sys.exit(1 if fails else 0)
