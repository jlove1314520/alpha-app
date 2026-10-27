# -*- coding: utf-8 -*-
"""先.八十-11（2026-10-12）：新聞排程本機補班。

根因（gh run list 實測）：news_events.yml 排程每 30 分鐘一次，但 GitHub 對高頻 schedule 是 best-effort，
實際每 4～7 小時才觸發一次（10/06～10/11 每次都 success，沒有失敗，是「沒被排上」），所以停擺自檢回報錯過 5 班。
本機 token 沒有 Actions 寫入權限（workflow dispatch 回 403），不能從本機叫雲端補跑。

做法：本機排程 AlphaNewsFallback 每 30 分鐘叫一次；先看 repo 裡（origin/main）data/news.json 的 fetched_at，
距今 ≥ STALE_MIN 才在本機跑同一套步驟（與 news_events.yml 完全相同的腳本、相同順序、相同 schema 守門），
再只提交 workflow 本來就提交的那幾個檔。雲端有準時跑時本機什麼都不做，不會兩邊搶寫。
不需要任何金鑰（workflow 本身也沒有用 secrets）。自身失敗只記 log（十二節）。
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import local_git_commit as G  # noqa: E402

TW = timezone(timedelta(hours=8))
STALE_MIN = 60
LOG = ROOT / "research" / "news_local_fallback.log"
# 與 .github/workflows/news_events.yml 相同的腳本；第一步失敗就停，其餘照 workflow 的 continue-on-error。
# 先.八十一-64（2026-10-13）：拆檔（split_events_by_code）改成緊接在 fetch_news_events 之後跑。
# 原本照 workflow 放最後，中間 news_body_extract 約 7 分鐘，這段時間工作區的 events.json 已是新版、
# events_search.json／events_by_code／ir_events 還是舊版（冒煙 #132 偶發失敗的根因）。拆檔只讀 events.json，
# 後面三步都不寫 events.json，所以提前跑輸出完全相同，不一致的時間從約 7 分鐘縮到拆檔本身的幾秒。
STEPS = [
    ([".github/scripts/fetch_news_events.py"], True),
    (["scripts/split_events_by_code.py"], False),
    ([".github/scripts/fetch_news_sitemap.py"], False),
    ([".github/scripts/news_body_extract.py"], False),
    (["scripts/build_themes.py"], False),
]
EVENTS_WRITERS = {".github/scripts/fetch_news_events.py"}  # 會寫 events.json 的步驟；自測確認拆檔緊接在最後一個之後
OUTPUTS = ["data/news.json", "data/news_by_code", "data/events.json", "data/events_by_code", "data/ir_events.json", "data/events_search.json", "data/news_urls.json", "data/news_evidence.json",
           "data/themes.json", "data/schema_guard/news_events.json"]


def log(msg: str) -> None:
    line = f"[{datetime.now(TW).strftime('%m-%d %H:%M')}] {msg}"
    print(line, flush=True)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def origin_age_min() -> float | None:
    G._g("fetch", "-q", "origin", "main", timeout=120)
    r = G._g("show", "origin/main:data/news.json", timeout=60)
    try:
        t = datetime.fromisoformat(json.loads(r.stdout)["fetched_at"])
        if t.tzinfo is None:
            t = t.replace(tzinfo=TW)
        return (datetime.now(TW) - t).total_seconds() / 60
    except Exception:  # noqa: BLE001
        return None


ACCUM = {"data/events.json": "events", "data/news_urls.json": "urls", "data/news_evidence.json": "evidence"}
SHRINK_MAX = 0.05  # 累積檔筆數比 HEAD 少超過 5% → 判定為「從空白重建」，本輪作廢


def _count(path: str, key: str, rev: str | None = None) -> int | None:
    try:
        txt = G._g("show", f"{rev}:{path}").stdout if rev else (ROOT / path).read_text(encoding="utf-8")
        return len(json.loads(txt).get(key) or [])
    except Exception:  # noqa: BLE001
        return None


def preflight_ok() -> str | None:
    """2026-10-13 事故防線①：repo 在 rebase 中、或累積檔讀不出 JSON → 不跑（腳本會把讀不出的檔當成沒有歷史而洗掉）。"""
    if G.rebase_in_progress():
        return "repo 正在 rebase 中"
    for p, k in ACCUM.items():
        if (ROOT / p).exists() and _count(p, k) is None:
            return f"{p} 不是合法 JSON"
    return None


def shrink_check() -> str | None:
    """事故防線②：跑完後累積檔筆數不得比 HEAD 少超過 5%。"""
    for p, k in ACCUM.items():
        old, new = _count(p, k, "HEAD"), _count(p, k)
        if old and (new is None or new < old * (1 - SHRINK_MAX)):
            return f"{p} 筆數 {old}→{new}"
    return None


SPLIT_STEP = ["scripts/split_events_by_code.py"]


def _split_fetched_at() -> dict:
    """events.json 與拆檔三檔（events_search／events_by_code/_index／ir_events）的 fetched_at；讀不到的記 None。"""
    def fa(path, top=False):
        try:
            d = json.loads((ROOT / path).read_text(encoding="utf-8"))
            return (d.get("top") or {}).get("fetched_at") if top else d.get("fetched_at")
        except Exception:  # noqa: BLE001
            return None
    return {"events": fa("data/events.json"), "search": fa("data/events_search.json", top=True),
            "index": fa("data/events_by_code/_index.json"), "ir": fa("data/ir_events.json")}


def ensure_split_same_batch(env, run=None) -> str:
    """先.一〇三-14x（2026-10-16）：別的排程 pull --autostash 期間，工作目錄裡本輪剛寫的 events.json 會暫時被收回 HEAD 版，
    這時跑的拆檔會拆出舊班（10:35 實例：events.json 10:35 版提交了，_index 還是 08:49 版 → 冒煙 #142 三檔不同班）。
    提交前比對 fetched_at，不同班就重跑一次拆檔。自身任何失敗只記警告、照常往下提交（十二節，fail open）。"""
    try:
        fa = _split_fetched_at()
        if fa["events"] and fa["search"] == fa["index"] == fa["ir"] == fa["events"]:
            return ""
        run = run or (lambda: subprocess.run([sys.executable, *SPLIT_STEP], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=600))
        r = run()
        fb = _split_fetched_at()
        same = bool(fb["events"]) and fb["search"] == fb["index"] == fb["ir"] == fb["events"]
        return f"拆檔與 events.json 不同班（{fa}）→ 重跑拆檔 exit={getattr(r, 'returncode', '?')}，{'已同班' if same else '仍不同班：' + str(fb)}"
    except Exception as e:  # noqa: BLE001
        return f"[warn] 同班檢查失敗（{type(e).__name__}: {e}），照常提交"


def main() -> int:
    why = preflight_ok()
    if why:
        log(f"不跑：{why}")
        return 0
    age = origin_age_min()
    # 先.一三五-1d（2026-10-27）：重大訊息長期歸檔（events.json 只留 90 天）。origin_age_min 已 fetch 過，
    # 工作目錄版＋origin/main 版都歸檔；零外部請求，輸出在 research/data/（不進 repo）。自身失敗只記 log（十二節）。
    try:
        import archive_mops_events as A
        log(f"重大訊息歸檔：新增 {A.run(['origin/main'])} 筆")
    except Exception as e:  # noqa: BLE001
        log(f"[warn] 重大訊息歸檔失敗：{type(e).__name__}: {e}")
    if age is not None and age < STALE_MIN:
        log(f"雲端 news.json {age:.0f} 分鐘前更新，不需補班")
        return 0
    log(f"雲端 news.json {'讀不到' if age is None else f'{age:.0f} 分鐘沒更新'} → 本機補班")
    env = dict(__import__("os").environ, PYTHONIOENCODING="utf-8")
    for args, must in STEPS:
        t0 = time.time()
        r = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=1800)
        log(f"  {args[0]} exit={r.returncode}（{time.time() - t0:.0f} 秒）")
        if r.returncode != 0 and must:
            log("  第一步失敗，本輪不提交：" + (r.stderr or r.stdout)[-300:].replace("\n", " "))
            return 0
    subprocess.run([sys.executable, "scripts/data_schema_guard.py", "guard", "--report", "data/schema_guard/news_events.json", "--label", "news_events"],
                   cwd=ROOT, capture_output=True, env=env, timeout=600)
    bad = shrink_check()
    if bad:
        G._g("checkout", "-q", "HEAD", "--", *[p for p in OUTPUTS if G._g("ls-files", "--error-unmatch", p).returncode == 0])
        log(f"  累積檔筆數異常縮水（{bad}），本機這輪作廢（產出檔還原）")
        return 0
    # 2026-10-13：提交前再看一次雲端；跑步驟的 7 分鐘內雲端已更新就作廢本機這輪（產出檔還原 HEAD），避免兩邊同時寫同一批檔而衝突
    age2 = origin_age_min()
    if age2 is not None and age2 < STALE_MIN:
        G._g("checkout", "-q", "HEAD", "--", *[p for p in OUTPUTS if G._g("ls-files", "--error-unmatch", p).returncode == 0])
        log(f"  雲端已在 {age2:.0f} 分鐘前更新，本機這輪作廢（產出檔還原）")
        return 0
    # 2026-10-21：同班檢查改在 git 鎖內做（commit_paths 的 under_lock），鎖外做會被別的排程 autostash 換掉檔案
    def _same_batch_under_lock():
        same = ensure_split_same_batch(env)
        if same:
            log("  " + same)
    res = G.commit_paths(OUTPUTS, f"新聞與事件：本機補班更新（雲端排程 {'未知' if age is None else f'{age:.0f} 分鐘'}未觸發，先.八十-11）",
                         drop_on_conflict=True, under_lock=_same_batch_under_lock)
    log("  提交：" + res)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        log(f"[warn] news_local_fallback 失敗：{type(e).__name__}: {e}")
        sys.exit(0)
