# -*- coding: utf-8 -*-
"""自選股日內分時匯出到 repo（先.一四九-2 甲，[預設放行] 零之二；提案 docs/PROPOSAL_INTRADAY_TW_OFFLINE.md）。

目的：手機連不到家裡電腦（本機 live server）時，自選股小圖仍能畫當日分時。
做法：只讀本機常駐 shioaji_quotes.py 已經寫好的熱檔 research/.live_state_sinopac.json，
      挑自選股（research/.live_watchlist.json）＋加權（TAIEX）＋櫃買（TPEX）的當日 1 分K，
      寫成 data/intraday_tw/YYYY-MM-DD.json 與 data/intraday_tw/index.json（只記最新日期），提交並推送。
- **零外部請求**：不碰 Shioaji、不打任何網路 API；不改 shioaji_quotes.py（免常駐服務重啟）。
- 由 scripts/quotes_local_fallback.py 台股分支（AlphaQuotesFallback，交易日 09:05～13:45 每 10 分鐘）在盤中時段呼叫，
  不新建排程；距上次匯出未滿 MIN_GAP_MIN 就略過（實際約每 20 分鐘一次），13:35 後一律再匯一次收盤完整版。
- 熱檔不是今天、或超過 HOT_STALE_MIN 沒更新（電腦關機／行程停）→ 不寫、不推。
- 自身任何失敗只回傳一行說明、不丟例外（十二節：不得拖垮呼叫端的報價備援）。
- 輸出路徑在 data/ 底下，已被 dev_queue_runner.MACHINE_WRITTEN 的 ^data/ 涵蓋（十節）。
- 先.一三五-1lv：另寫首頁用精簡檔 YYYY-MM-DD.spark.json（每 5 分鐘取樣、只留時間＋收盤，最後一根一定保留），
  index.json 的 spark 欄位指向它；首頁小圖只讀精簡檔（完整 1 分K 盤中一路長大到約 80KB，撐爆冒煙 #78 首頁載入量 350KB 門檻）。
  完整檔照舊寫，留給要看完整 1 分K 的地方。
- [自行裁量] 提案寫「舊檔每天刪」，本版先不刪（刪除屬不可逆類，留待 Cowork 決定）；每日約 85KB。
用法：python scripts/export_intraday_tw.py [--no-commit] [--force]
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TW = timezone(timedelta(hours=8))
HOT = ROOT / "research" / ".live_state_sinopac.json"
WATCH = ROOT / "research" / ".live_watchlist.json"
OUT_DIR = "data/intraday_tw"
INDEX_CODES = ["TAIEX", "TPEX"]
MIN_GAP_MIN = 14
HOT_STALE_MIN = 20
FINAL_AFTER = "13:35"


def _hm(t: str) -> str:
    return t[11:16]


def build(now: datetime) -> tuple[dict | None, str]:
    day = now.strftime("%Y-%m-%d")
    try:
        hot = json.loads(HOT.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return None, f"讀不到熱檔（{type(e).__name__}）"
    try:
        upd = datetime.fromisoformat(hot.get("updated_at"))
        if upd.tzinfo is None:
            upd = upd.replace(tzinfo=TW)
    except Exception:  # noqa: BLE001
        return None, "熱檔沒有 updated_at"
    if upd.astimezone(TW).strftime("%Y-%m-%d") != day:
        return None, f"熱檔不是今天（{hot.get('updated_at')}）"
    age = (now - upd).total_seconds() / 60
    if age > HOT_STALE_MIN and now.strftime("%H:%M") < FINAL_AFTER:
        return None, f"熱檔 {age:.0f} 分鐘沒更新"
    try:
        wl = [str(c) for c in (json.loads(WATCH.read_text(encoding="utf-8")).get("codes") or [])]
    except Exception:  # noqa: BLE001
        wl = []
    codes = [c for c in wl if c.isalnum()] + INDEX_CODES
    kb = hot.get("kbars") or {}
    bars = {}
    for c in dict.fromkeys(codes):
        rows = [[_hm(b["t"]), b.get("o"), b.get("h"), b.get("l"), b.get("c"), b.get("v")]
                for b in (kb.get(c) or []) if isinstance(b, dict) and str(b.get("t", "")).startswith(day) and b.get("c") is not None]
        if rows:
            bars[c] = rows
    if not bars:
        return None, "熱檔裡沒有自選股的當日 1 分K"
    doc = {"date": day, "generated_at": now.isoformat(timespec="seconds"), "hot_updated_at": hot.get("updated_at"),
           "source": "shioaji-local", "interval": "1m",
           "columns": ["time", "open", "high", "low", "close", "volume"],
           "note": "家裡電腦從 Shioaji 熱檔匯出，約每 20 分鐘上傳一次；非投資建議（先.一四九-2）",
           "bars": bars}
    return doc, "ok"


SPARK_STEP_MIN = 5


def spark_doc(doc: dict) -> dict:
    """首頁小圖用精簡檔：每 SPARK_STEP_MIN 分鐘取一根（分鐘數整除者）＋第一根＋最後一根，只留 [時間, 收盤]。"""
    ci = (doc.get("columns") or []).index("close") if "close" in (doc.get("columns") or []) else 4
    bars = {}
    for code, rows in (doc.get("bars") or {}).items():
        keep = [r for i, r in enumerate(rows)
                if i == 0 or i == len(rows) - 1 or (str(r[0])[3:5].isdigit() and int(str(r[0])[3:5]) % SPARK_STEP_MIN == 0)]
        bars[code] = [[r[0], r[ci]] for r in keep]
    return {"date": doc.get("date"), "generated_at": doc.get("generated_at"), "hot_updated_at": doc.get("hot_updated_at"),
            "source": doc.get("source"), "interval": f"{SPARK_STEP_MIN}m", "columns": ["time", "close"],
            "note": f"首頁小圖用精簡檔：完整 1 分K 每 {SPARK_STEP_MIN} 分鐘取樣、只留收盤（最後一根必留）；非投資建議（先.一三五-1lv）",
            "bars": bars}


def run(now: datetime | None = None, commit: bool = True, force: bool = False) -> str:
    try:
        now = now or datetime.now(TW)
        day, hm = now.strftime("%Y-%m-%d"), now.strftime("%H:%M")
        out = ROOT / OUT_DIR / f"{day}.json"
        prev = None
        if out.exists():
            try:
                prev = json.loads(out.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                prev = None
        if prev and not force:
            gap = (now - datetime.fromisoformat(prev["generated_at"])).total_seconds() / 60
            final_done = str(prev.get("generated_at", ""))[11:16] >= FINAL_AFTER
            if final_done:
                return "skip_final_done"
            if gap < MIN_GAP_MIN and hm < FINAL_AFTER:
                return f"skip_gap（上次 {gap:.0f} 分鐘前）"
        doc, why = build(now)
        if doc is None:
            return "skip_" + why
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
        spark = ROOT / OUT_DIR / f"{day}.spark.json"
        spark.write_text(json.dumps(spark_doc(doc), ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
        idx = ROOT / OUT_DIR / "index.json"
        idx.write_text(json.dumps({"latest": day, "spark": spark.name, "generated_at": doc["generated_at"], "codes": sorted(doc["bars"])},
                                  ensure_ascii=False), encoding="utf-8", newline="\n")
        n = sum(len(v) for v in doc["bars"].values())
        if not commit:
            return f"written（{len(doc['bars'])} 檔、{n} 根，未提交）"
        sys.path.insert(0, str(ROOT / "scripts"))
        import local_git_commit as G  # noqa: PLC0415
        res = G.commit_paths([f"{OUT_DIR}/{day}.json", f"{OUT_DIR}/{day}.spark.json", f"{OUT_DIR}/index.json"],
                             f"自選股日內分時：本機熱檔匯出 {day} {hm}（{len(doc['bars'])} 檔，先.一四九-2）",
                             drop_on_conflict=True)
        return f"exported（{len(doc['bars'])} 檔、{n} 根）：{res}"
    except Exception as e:  # noqa: BLE001
        return f"error（{type(e).__name__}: {e}）"


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(run(commit="--no-commit" not in sys.argv, force="--force" in sys.argv))
