# -*- coding: utf-8 -*-
"""量測新聞產出率（試水溫，2026-09-09 總司令選項 3）。

**要回答的問題**：抓 N 則新聞能產出幾句可用的題材證據？
以及**哪個來源的產出率高**——這決定常態要抓哪些、不抓哪些。

現在只有一個外推值（180 篇 → 12 句），樣本太小而且是 RSS 混合樣本。
sitemap 收到 3,537 則，全抓要約 2 小時，先取樣量真實產出率再決定。

**分來源量**是重點：中央社財經是精選的產經新聞、Yahoo 是全分類混雜，
兩者產出率可能差很多。如果 Yahoo 的產出率低很多，
常態就只抓中央社，省下大部分時間。
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".github" / "scripts"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
OUT = D / "news_yield_sample.json"

CNA_SAMPLE = 145      # 中央社財經全抓（本來就只有這麼多）
YAHOO_SAMPLE = 200    # Yahoo 隨機抽樣


def main() -> int:
    from news_body_extract import fetch_body, split_sentences, pattern_hit, PATTERNS
    from news_matcher import load_company_names, load_active_codes, match_article

    urls = json.loads((D / "news_urls.json").read_text(encoding="utf-8"))["urls"]
    kwdoc = json.loads((D / "seed" / "theme_keywords.json").read_text(encoding="utf-8"))
    theme_kw = {tid: v["keywords"] for tid, v in (kwdoc.get("themes") or {}).items()}
    name2code, _amb = load_company_names()
    active = load_active_codes()

    cna = [u for u in urls if u["source"] == "中央社"][:CNA_SAMPLE]
    yh = [u for u in urls if u["source"] == "Yahoo股市"]
    random.seed(20260909)
    yh = random.sample(yh, min(YAHOO_SAMPLE, len(yh)))
    sample = cna + yh
    print(f"取樣 {len(sample)} 則（中央社財經 {len(cna)}、Yahoo 隨機 {len(yh)}）")
    print(f"預估耗時 {len(sample) * 2 / 60:.0f} 分鐘\n")

    stats = defaultdict(lambda: {"fetched": 0, "body_ok": 0, "with_stock": 0,
                                 "with_quote": 0, "quotes": 0})
    theme_hits = Counter()
    rows = []
    for i, u in enumerate(sample, 1):
        src = u["source"]
        st = stats[src]
        st["fetched"] += 1
        try:
            body = fetch_body(u["url"])
        except Exception:  # noqa: BLE001
            continue
        if not body:
            continue
        st["body_ok"] += 1
        m = match_article("", body, name2code, active)
        codes = set(m["codes"])
        if not codes:
            continue
        st["with_stock"] += 1
        qs = []
        for sent in split_sentences(body):
            for tid, kws in theme_kw.items():
                k = next((kk for kk in kws if kk in sent), None)
                if not k:
                    continue
                in_sent = {c for c in codes
                           if c in sent or any(nm in sent and cc == c
                                               for nm, cc in name2code.items())}
                if not in_sent:
                    continue
                frag = pattern_hit(sent, [k], PATTERNS)
                if not frag:
                    continue
                qs.append({"theme_id": tid, "codes": sorted(in_sent),
                           "pattern": frag, "quote": sent[:160]})
                theme_hits[tid] += 1
                break
        if qs:
            st["with_quote"] += 1
            st["quotes"] += len(qs)
            rows.append({"url": u["url"], "source": src, "quotes": qs[:6]})
        if i % 50 == 0:
            print(f"  ...已處理 {i}/{len(sample)}")

    OUT.write_text(json.dumps({"sample": rows}, ensure_ascii=False,
                              separators=(",", ":")), encoding="utf-8")
    print("\n" + "=" * 62)
    print("  產出率量測結果")
    print("=" * 62)
    print(f"  {'來源':<10}{'抓取':>6}{'有內文':>8}{'命中個股':>10}{'有題材句':>10}{'句數':>7}{'每百篇句數':>12}")
    for src, st in stats.items():
        per100 = st["quotes"] / st["fetched"] * 100 if st["fetched"] else 0
        print(f"  {src:<10}{st['fetched']:>6}{st['body_ok']:>8}{st['with_stock']:>10}"
              f"{st['with_quote']:>10}{st['quotes']:>7}{per100:>12.1f}")
    tot_f = sum(s["fetched"] for s in stats.values())
    tot_q = sum(s["quotes"] for s in stats.values())
    print(f"\n  合計 {tot_f} 篇 → {tot_q} 句"
          f"（每百篇 {tot_q / tot_f * 100 if tot_f else 0:.1f} 句）")
    tn = {tid: v["name"] for tid, v in (kwdoc.get("themes") or {}).items()}
    print(f"\n  命中的題材（前 10）：")
    for tid, n in theme_hits.most_common(10):
        print(f"    {tn.get(tid, tid):16s} {n} 句")
    print(f"\n  → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
