# -*- coding: utf-8 -*-
"""題材成員驗證與上線（題材庫實作二 / 驗證 v2，2026-09-08）。

**v1 為什麼不通**（總司令自我更正，實測證實）：
v1 的 A 級要求「公司在 MOPS 自述屬於某題材」——**但公司從不這樣講**。
公司公告講的是**產品、業務、客戶、擴產、接單**。
實測 123 個題材只驗出 1 筆，還是最不相干的一筆
（2881 富邦金→金控，證據是「發行公司債」公告，純粹因為公司名含「金控」二字）。

**v2 的核心改變：對映的左邊改成「產品／業務名詞」，不是「題材名」。**
「取得先進封裝設備訂單」「CoWoS 產能擴充」「投入玻璃基板研發」→ 對映到對應題材。

三項規則（總司令指定）：
1. **A 級**＝公司公開文件中描述**自身產品／業務／客戶／擴產／接單**的內容。
   來源限已合規管線：MOPS 重大訊息、法說會公告、月營收公告說明。
2. **對映表獨立成檔** `data/seed/theme_keywords.json`——
   **可稽核、可擴充、改規則不用改程式**。埋在程式裡的規則沒有人會去看。
3. **C 級**＝新聞陳述，門檻為
   「**≥2 篇不同網域**」**或**「**單篇但同時命中題材關鍵詞與公司名，且句型明確**」。
   單篇者標 `confidence: "low"`，畫面上以較淡樣式呈現並註明「單一來源」。

**append-only 鐵律**：既有 membership 的 `effective_from` 一律沿用，
**禁止回頭改寫歷史歸屬**。新證據只新增或升級等級，不竄改生效日。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".github" / "scripts"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
SEED = D / "seed" / "seed_themes_validated.json"
KWMAP = D / "seed" / "theme_keywords.json"
OUT = D / "themes.json"
TZ = timezone(timedelta(hours=8))

MIN_C_DOMAINS = 2
# 總司令點名的八個題材，驗收要逐一回報卡在哪裡
SPOTLIGHT = ["adv_package", "glass_substrate", "pcb", "ccl",
             "ic_design", "thermal", "probe_card", "ai_server"]


def _source_key(text: str) -> str:
    """同文轉載偵測用的來源鍵（題材二.2）。

    **同一篇稿被多家媒體轉載時，網域數會膨脹，但真正的來源只有一個。**
    用「兩個網域」當獨立性門檻在這種情況下會被繞過——
    實測 2330→光罩 就是這樣過關的：中央社原稿 + Yahoo 轉載，
    看起來是 2 個網域，其實是同一則報導。

    做法：把文字正規化（去空白、全形轉半形、去括號內容與標點）後取雜湊。
    雜湊相同就視為同一來源，不論網域幾個。
    """
    t = unicodedata.normalize("NFKC", text or "")
    # **只去括號字元、保留內容**。第一版把括號內容整段刪掉，結果
    # 「…光罩 專家：輝達」與「…光罩（專家：輝達）」會得到不同雜湊——
    # 跟本意正好相反（單元測試抓到的）。轉載常見的差異是加減括號、
    # 不是換掉內容，所以要保留內容才對得起來。
    t = re.sub(r"[（(\[【《）)\]】》]", "", t)
    t = re.sub(r"[\s　]+", "", t)               # 去所有空白
    t = re.sub(r"[，。、；：！？「」『』…—－·,.;:!?\"'-]", "", t)
    return hashlib.sha1(t.encode("utf-8")).hexdigest()[:16]


def _load(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def build_keyword_map(themes: list) -> tuple[dict, dict]:
    """theme_id → 關鍵詞清單。規則檔優先，沒列到的沿用種子表自帶的 kw。"""
    ext = (_load(KWMAP, {}) or {}).get("themes") or {}
    out, source = {}, {}
    for t in themes:
        tid = t["id"]
        if tid in ext and ext[tid].get("keywords"):
            out[tid] = list(ext[tid]["keywords"])
            source[tid] = "規則檔（已擴充同義詞與產品名）"
        else:
            out[tid] = [k for k in (t.get("kw") or []) if k]
            source[tid] = "種子表原始 kw（尚未擴充）"
    return out, source


def load_patterns() -> list:
    d = _load(KWMAP, {}) or {}
    return (d.get("sentence_patterns") or {}).get("patterns") or []


def pattern_hit(text: str, theme_kw: list, patterns: list) -> str | None:
    """句型明確？回傳命中的句型樣態，沒有回 None。

    只要文字裡出現「<句型前綴>+<題材關鍵詞>」的組合就算——
    例如 patterns 有「打入{theme}供應鏈」、關鍵詞有「CoWoS」，
    文字含「打入CoWoS供應鏈」即命中。
    """
    for kw in theme_kw:
        for pat in patterns:
            frag = pat.replace("{theme}", kw).replace("{code}", "")
            frag = frag.strip()
            if frag and frag in text:
                return frag
    return None


def main() -> int:
    seed = _load(SEED)
    if not seed:
        print(f"! 找不到 {SEED.name}，先跑 scripts/validate_seed_themes.py")
        return 1
    themes = seed.get("themes") or []
    kwmap, kwsrc = build_keyword_map(themes)
    patterns = load_patterns()
    news = (_load(D / "news.json", {}) or {}).get("news") or []
    events = (_load(D / "events.json", {}) or {}).get("events") or []
    prior_ms = {(m["code"], m["theme_id"]): m
                for m in ((_load(OUT, {}) or {}).get("memberships") or [])}
    # 2026-09-09（v3）內文題材句。這是唯一能表達「這家公司做這件事」的素材——
    # 標題只講漲跌與價格，題材詞彙全在內文（實測 300 則標題裡 11 個題材詞 0 次）。
    body_ev = (_load(D / "news_evidence.json", {}) or {}).get("evidence") or []

    try:
        from news_matcher import load_company_names, load_active_codes, match_article
        name2code, _amb = load_company_names()
        active = load_active_codes()
    except Exception as e:  # noqa: BLE001
        print(f"! news_matcher 載入失敗（{type(e).__name__}: {e}）")
        return 1

    ev_by_code = defaultdict(list)
    for e in events:
        if e.get("code"):
            ev_by_code[e["code"]].append(e)

    news_hits = []
    for n in news:
        m = match_article(n.get("title", ""), n.get("body", ""), name2code, active)
        if m["codes"]:
            news_hits.append((n, set(m["codes"]),
                              (n.get("title", "") or "") + (n.get("body", "") or "")))

    today = datetime.now(TZ).strftime("%Y-%m-%d")
    memberships = []
    stats = {"A": 0, "C": 0, "C_low": 0, "D_only": 0}
    per_theme = defaultdict(lambda: {"A": 0, "C": 0})
    # 卡點診斷：這個題材的關鍵詞在素材裡出現過嗎？
    blocked = {}

    for t in themes:
        tid = t["id"]
        kws = kwmap[tid]
        kw_seen_in_news = any(any(k in txt for k in kws) for _, _, txt in news_hits)
        kw_seen_in_events = any(any(k in (e.get("title") or "") for k in kws)
                                for lst in ev_by_code.values() for e in lst)
        for code in t["members"]:
            level, conf, evidence = None, None, []

            # ── A 級：公司自身公告描述產品／業務／擴產／接單 ──────────────
            for e in ev_by_code.get(code, []):
                title = e.get("title", "") or ""
                hit = next((k for k in kws if k in title), None)
                if hit:
                    level = "A"
                    evidence.append({"level": "A", "matched": hit,
                                     "type": e.get("type"), "date": e.get("date"),
                                     "url": e.get("url"), "quote": title[:140]})
                    if len(evidence) >= 3:
                        break

            # ── C 級之一：內文題材句 ──────────────────────────────────────
            # 2026-09-09（題材二）三項修正：
            # (1) **補上網域檢查**，跟標題路徑同一把尺。原本內文路徑一命中就標
            #     normal，等於內文證據的門檻比標題證據鬆——同一個等級兩套標準。
            # (2) **同文轉載偵測**：同一篇稿被多家轉載，網域數會膨脹但**來源只有一個**。
            #     以正規化標題的雜湊當來源鍵，雜湊相同者視為同一來源。
            # (3) 句型由 news_body_extract 強制（關係方向要求），這裡不再放行無句型者。
            if level != "A":
                c_ev, doms, srckeys = [], set(), set()
                for ev in body_ev:
                    for q in ev.get("quotes") or []:
                        if q.get("theme_id") != tid or code not in (q.get("codes") or []):
                            continue
                        if not q.get("pattern"):
                            continue          # 沒句型＝純共現，不採
                        doms.add(urlparse(ev.get("url", "")).netloc)
                        srckeys.add(_source_key(q.get("quote", "")))
                        c_ev.append({
                            "level": "C", "matched": q.get("matched"),
                            "pattern": q.get("pattern"), "source": ev.get("source"),
                            "date": ev.get("date"), "url": ev.get("url"),
                            "quote": q.get("quote", "")[:160],
                        })
                if c_ev:
                    # **獨立來源數以「去轉載後的來源鍵」為準，不是網域數**
                    level = "C"
                    conf = "normal" if len(srckeys) >= MIN_C_DOMAINS else "low"
                    evidence = c_ev[:3]

            # ── C 級之二：標題層。≥2 網域，或單篇但句型明確 ───────────────
            if level != "A" and not evidence:
                doms, srckeys, c_ev, pat_ev = set(), set(), [], None
                for n, codes, txt in news_hits:
                    if code not in codes:
                        continue
                    hit = next((k for k in kws if k in txt), None)
                    if not hit:
                        continue
                    frag = pattern_hit(txt, kws, patterns)
                    # 2026-09-09（題材二.3）**關係方向要求同樣適用標題路徑。**
                    # 只修內文路徑不夠——實測 2330→光罩 就是從這條進來的，
                    # 句型欄位是 None（純共現），靠「兩個網域」就過關了。
                    # 「台積電攜ASML開發12吋光罩」只證明兩者被寫在同一句，
                    # 不證明台積電做光罩。沒有句型一律不採。
                    if not frag:
                        continue
                    doms.add(urlparse(n.get("url", "")).netloc)
                    # 題材二.2 同文轉載：以正規化標題的雜湊當來源鍵
                    srckeys.add(_source_key(n.get("title") or ""))
                    if not pat_ev:
                        pat_ev = frag
                    c_ev.append({"level": "C", "matched": hit, "pattern": frag,
                                 "source": n.get("source"),
                                 "date": (n.get("published") or "")[:16],
                                 "url": n.get("url"), "quote": (n.get("title") or "")[:140]})
                # **獨立性以去轉載後的來源鍵計，不是網域數**
                if len(srckeys) >= MIN_C_DOMAINS:
                    level, conf, evidence = "C", "normal", c_ev[:3]
                elif c_ev and pat_ev:
                    # 單篇但句型明確：採用但標低信心，畫面要淡化並註明「單一來源」
                    level, conf, evidence = "C", "low", c_ev[:3]

            key = (code, tid)
            if level:
                stats[level] += 1
                if conf == "low":
                    stats["C_low"] += 1
                per_theme[tid][level] += 1
                memberships.append({
                    "code": code, "theme_id": tid, "level": level,
                    "confidence": conf or "normal",
                    "weight": None,
                    "weight_note": "unknown（營收比重來源受條款封鎖，見 DATA_SOURCE_MAP）",
                    "effective_from": prior_ms.get(key, {}).get("effective_from", today),
                    "evidence": evidence, "evidence_count": len(evidence),
                })
            else:
                stats["D_only"] += 1
        if not per_theme[tid]["A"] and not per_theme[tid]["C"]:
            blocked[tid] = ("關鍵詞在新聞/公告裡從未出現——素材池裡根本沒有這則報導"
                            if not (kw_seen_in_news or kw_seen_in_events)
                            else "關鍵詞出現過，但沒有和候選成員同時命中")

    verified = {tid for tid, v in per_theme.items() if v["A"] or v["C"]}
    doc = {
        "meta": {
            "generated_at": datetime.now(TZ).isoformat(),
            "version": "v2（產品／業務 → 題材對映）",
            "keyword_map": "data/seed/theme_keywords.json（獨立規則檔，可稽核可擴充）",
            "evidence_rule": "A＝公司公告描述自身產品/業務/擴產/接單；"
                             f"C＝新聞，≥{MIN_C_DOMAINS} 個不同網域，或單篇但句型明確（標低信心）；"
                             "D＝模型推斷，永不單獨顯示",
            "append_only": "effective_from 沿用既有值，禁止改寫歷史歸屬",
            "disclosure": "本題材庫由公開資訊與模型推斷建立、以公司公開文件與新聞驗證；"
                          "未收錄不代表無關聯。",
            "themes_total": len(themes),
            "themes_with_verified_member": len(verified),
            "members_A": stats["A"], "members_C": stats["C"],
            "members_C_low_confidence": stats["C_low"],
            "candidates_unverified_D": stats["D_only"],
            "news_pool": len(news), "news_hit_stock": len(news_hits),
            "events_pool": len(events),
        },
        "themes": [{k: v for k, v in t.items() if k != "members_dropped"} for t in themes],
        "memberships": memberships,
        "blocked_reasons": blocked,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    tn = {t["id"]: t["name"] for t in themes}
    print("=" * 66)
    print("  題材成員驗證 v2（產品／業務 → 題材）")
    print("=" * 66)
    print(f"  題材總數 {len(themes)}｜**至少一檔通過的題材：{len(verified)}**")
    print(f"  成員：A 級 {stats['A']}、C 級 {stats['C']}"
          f"（其中低信心單篇 {stats['C_low']}）｜合計 {stats['A'] + stats['C']}")
    print(f"  仍為 D 級未驗證（不顯示）：{stats['D_only']}")
    print(f"  素材：新聞 {len(news)} 則（命中個股 {len(news_hits)}）、事件 {len(events)} 筆")
    print()
    print("  八個點名題材：")
    for tid in SPOTLIGHT:
        v = per_theme.get(tid, {"A": 0, "C": 0})
        tot = v["A"] + v["C"]
        mark = "✅" if tot else "❌"
        why = "" if tot else f"　卡點：{blocked.get(tid, '?')}"
        print(f"    {mark} {tn.get(tid, tid):12s} 驗出 {tot} 檔"
              f"（A{v['A']}/C{v['C']}）｜關鍵詞來源：{kwsrc.get(tid, '?')}{why}")
    print(f"\n  → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
