# -*- coding: utf-8 -*-
"""稽核管線自檢（2026-09-17 總司令裁示【記一筆】：監控工具自己也要被監控）。

**為什麼需要這支**：2026-09-10 commit `52ab79a7` 誤刪 `data_audit.py` 的
`TWSE_COMPANY` 常數，導致 `build_listed_universe.py` 第一步就
`ImportError`，`audit.yml` 連續一週（09-10~09-17）每次觸發都全滅——
但 `data/audit_report.json` 本身完全沒有留下任何紀錄，因為
`data_audit.py` 根本沒機會跑到寫檔那一步，只有去查 `gh run list` 才看
得到。稽核本來是用來抓別人靜默停擺的，結果自己靜默停擺卻沒有任何機制
記錄下來——這支就是補這個盲點。

**設計原則：極簡，只用標準函式庫，不 import 任何專案自己的模組去做
「檢查」**——如果連自我檢查都要 import 專案模組，那個模組壞掉時自我
檢查本身也會一起死，等於沒做。改用 `subprocess` 開一個乾淨的
`python -c` 子行程去試 import，子行程掛掉不會拖累這支腳本本身，
也不會拖累外層 workflow 繼續跑後面的步驟（`main()` 永遠 exit 0）。

**用法**：`python scripts/audit_preflight.py`，放在 `audit.yml` 最前面、
`build_listed_universe.py` 之前執行。結果寫進 `data/audit_report.json`
固定的 `self_check` 欄位（跟 `local_task_health` 同一套「讀出來只改
自己的 key」手法，不覆蓋其他稽核結果）。

**維護提醒**：`CHECKS` 列的是後面幾支腳本實際會用到的 import／常數——
那幾支腳本的 import 來源改了，這裡要跟著更新，否則會出現「自我檢查
過關，但實際腳本還是 ImportError」的假陽性。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "audit_report.json"
TZ = timezone(timedelta(hours=8))

# ── 合規.三（2026-09-20總司令裁示【緊急·合規】）：黑名單網域靜態掃描 ──
# 背景：2026-09-19一支新腳本（`material_disclosure_order_win_count.py`）
# 對robots.txt全站Disallow的`mopsov.twse.com.tw`發出100次請求，繞過了
# 「防呆綁在既有四支client上」的舊機制。合規.二把防呆改成網域層
# （`research/net_guard.py`），這裡是第二道防線：**規則寫在CLAUDE.md/
# net_guard.py，但沒有機器在檢查『新腳本是否真的import了net_guard』**，
# 這支掃描補上這個盲點——commit/稽核時就能看到，不用等下一次真的打出去
# 才發現。
#
# 刻意用「讀net_guard.py原始碼文字、regex抓DOMAIN_BLOCKLIST裡的字串」
# 取得黑名單，不`import net_guard`——沿用本檔開頭說的設計原則：自我檢查
# 不依賴被檢查對象本身是否還能正常import。


def _load_blocklisted_domains() -> list[str]:
    ng_path = ROOT / "research" / "net_guard.py"
    try:
        text = ng_path.read_text(encoding="utf-8")
    except OSError:
        return []
    m = re.search(r"DOMAIN_BLOCKLIST[^=]*=\s*frozenset\(\{(.*?)\}\)", text, re.S)
    if not m:
        return []
    return re.findall(r'"([a-zA-Z0-9_.-]+\.[a-zA-Z]{2,})"', m.group(1))


def scan_domain_blocklist_strings() -> dict:
    """掃repo全部.py（排除net_guard.py/test_net_guard.py本身——那裡定義／
    測試黑名單字串是預期行為，不是違規），找出任何硬寫黑名單網域字串的
    檔案與行號。同一個檔案若有`import net_guard`，視為「已知情況，已掛
    網域層防呆」（guarded=True，仍列出但不算unguarded）；沒有的視為
    `unguarded`（可能是完全沒接防呆的新腳本，這是要抓的重點）。"""
    domains = _load_blocklisted_domains()
    exempt_files = {"net_guard.py", "test_net_guard.py"}
    hits: list[dict] = []
    for py_file in sorted(ROOT.rglob("*.py")):
        if py_file.name in exempt_files:
            continue
        if any(part in {".git", "node_modules", "__pycache__"} for part in py_file.parts):
            continue
        try:
            text = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not any(d in text for d in domains):
            continue
        guarded = "import net_guard" in text
        rel = py_file.relative_to(ROOT).as_posix()
        for lineno, line in enumerate(text.splitlines(), start=1):
            for d in domains:
                if d in line:
                    hits.append({"file": rel, "line": lineno, "domain": d, "guarded": guarded})
    unguarded = [h for h in hits if not h["guarded"]]
    return {
        "domains": domains,
        "hits": hits,
        "unguarded_count": len(unguarded),
        "unguarded": unguarded,
    }

CHECKS = [
    ("build_listed_universe.py 所需 import/常數",
     "import sys; sys.path.insert(0,'scripts'); "
     "from data_audit import TPEX_QUOTES, TWSE_COMPANY, TWSE_STOCK_DAY_ALL, "
     "is_stock_code, make_session, num"),
    ("prune_delisted.py 可以 import",
     "import sys; sys.path.insert(0,'scripts'); import prune_delisted"),
    ("data_audit.py 可以 import",
     "import sys; sys.path.insert(0,'scripts'); import data_audit"),
]


def run_check(label: str, code: str) -> dict:
    try:
        p = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
        ok = p.returncode == 0
        return {"label": label, "ok": ok, "error": "" if ok else (p.stderr or "").strip()[-500:]}
    except Exception as e:  # noqa: BLE001
        return {"label": label, "ok": False, "error": f"{type(e).__name__}: {e}"}


def check_queue_depth_sync() -> dict:
    """2026-09-20總司令裁示【Q4前視與#23無法重現】四：`CLAUDE.md`/
    `scripts/dev_queue_runner.py`/兩份`research/*_CONTINUATION_
    PROMPT.txt`過去各自硬寫佇列深度門檻數字，2026-09-19門檻從5改12時
    只有部分位置同步更新，兩份靜態prompt停留在舊版整整5輪都沒被發現。
    根因修法（`research/sync_continuation_prompts.py`）之後，這裡是
    最後一道防線：定期用子行程呼叫該腳本的`--check`模式，確認兩份
    prompt檔跟`research/queue_depth_config.py`（單一事實來源）仍然
    一致，不一致就alert——沿用本檔案「用子行程隔離、不import專案模組」
    的既有設計原則。"""
    try:
        p = subprocess.run(
            [sys.executable, "research/sync_continuation_prompts.py", "--check"],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        synced = p.returncode == 0 and "SYNCED" in p.stdout
        return {"ok": synced, "stdout": p.stdout.strip()[-500:],
                "error": "" if synced else (p.stderr or "").strip()[-500:]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def run_reproducibility_check() -> dict:
    """2026-09-20總司令裁示【Q4前視與#23無法重現】二.3：`#23`的
    `piotroski_fscore_sanity.py`/`piotroski_fscore_gate_v1.py`從
    2026-09-03起就`import`一個從未定義過的函式，兩支腳本從那天起就
    無法執行，但沒有任何機制發現，直到2026-09-20研究財報原子庫PIT
    機制時才意外撞見——**登記過的結果，要有機器定期確認它還跑得動**。
    掛進每日audit（`audit.yml`一天一次，非高頻），呼叫`research/
    reproducibility_check.py`批次試import`TRIALS_LEDGER.md`提到的
    全部腳本，抓出新的dangling import。逾時給5分鐘（180支腳本×10秒
    子行程逾時的最壞情況遠低於這個預算，正常情況幾分鐘內完成）。
    **`--skip-rerun`**：這裡刻意跳過2026-09-20新增的「結果重現抽查」
    （隨機抽10筆實際重跑比對數字，每筆逾時90秒，最壞情況再加15分鐘），
    daily audit只做輕量的import層級檢查；結果重現抽查成本較高、且每次
    抽樣結果不同，適合當人工觸發的稽核工具（`python research/
    reproducibility_check.py`不加旗標即可跑完整版），不適合綁進每日
    自動排程無限期重複跑。"""
    try:
        p = subprocess.run(
            [sys.executable, "research/reproducibility_check.py", "--skip-rerun"],
            cwd=ROOT, capture_output=True, text=True, timeout=300,
        )
        result_path = ROOT / "research" / "reproducibility_check_result.json"
        if not result_path.exists():
            return {"ok": False, "error": "reproducibility_check.py執行完但沒有產出"
                                            "reproducibility_check_result.json"}
        data = json.loads(result_path.read_text(encoding="utf-8"))
        broken = data.get("broken", [])
        return {"ok": len(broken) == 0, "n_checked": data.get("n_checked", 0),
                "by_status_count": data.get("by_status_count", {}), "broken": broken}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "reproducibility_check.py超過5分鐘未完成"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def main() -> int:
    now = datetime.now(TZ)
    results = [run_check(label, code) for label, code in CHECKS]
    all_ok = all(r["ok"] for r in results)

    try:
        doc = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    except (OSError, json.JSONDecodeError):
        doc = {}
    if not isinstance(doc, dict):
        doc = {}
    doc["self_check"] = {
        "checked_at": now.isoformat(),
        "ok": all_ok,
        "checks": results,
        "note": "audit.yml 每次執行最前面跑，確認後面幾支腳本要用到的 import/常數"
                "撈得到——2026-09-10~17 因 data_audit.py 誤刪 TWSE_COMPANY 導致"
                "build_listed_universe.py 連續一週 ImportError 全滅，但"
                "audit_report.json 本身完全沒有任何紀錄，只能靠 gh run list 才查得到，"
                "這個欄位就是補這個盲點。",
    }

    domain_scan = scan_domain_blocklist_strings()
    doc["domain_blocklist_scan"] = {
        "checked_at": now.isoformat(),
        "domains": domain_scan["domains"],
        "hit_count": len(domain_scan["hits"]),
        "unguarded_count": domain_scan["unguarded_count"],
        "unguarded": domain_scan["unguarded"],
        "hits": domain_scan["hits"],
        "note": "2026-09-20合規.三：掃repo全部.py找黑名單網域硬寫字串"
                "（黑名單來源research/net_guard.py::DOMAIN_BLOCKLIST）。"
                "unguarded=True代表該檔案提到黑名單網域卻沒有`import "
                "net_guard`，是最可能重演2026-09-19 mopsov違規事件的檔案，"
                "由check_external_connectivity.py轉成local_task_health告警。",
    }

    queue_sync = check_queue_depth_sync()
    doc["queue_depth_sync"] = {
        "checked_at": now.isoformat(),
        "ok": queue_sync["ok"],
        "detail": queue_sync,
        "note": "2026-09-20【Q4前視與#23無法重現】四：確認兩份*_CONTINUATION_"
                "PROMPT.txt跟research/queue_depth_config.py（單一事實來源）"
                "仍然一致，避免重演2026-09-19門檻更正只同步部分位置、"
                "連續5輪沒觸發補件規則的問題。",
    }

    repro = run_reproducibility_check()
    doc["reproducibility_check"] = {
        "checked_at": now.isoformat(),
        "ok": repro.get("ok", False),
        "detail": repro,
        "note": "2026-09-20【Q4前視與#23無法重現】二.3：批次確認"
                "TRIALS_LEDGER.md登記過結果的腳本現在還能不能import，"
                "是#23（piotroski_fscore_sanity.py自2026-09-03起dangling "
                "import從未被發現）的根本預防。",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    for r in results:
        print(("OK " if r["ok"] else "FAIL ") + r["label"] + (f"：{r['error']}" if not r["ok"] else ""))
    if not all_ok:
        print("::error::稽核管線自檢失敗，後面步驟可能會 ImportError")
    if domain_scan["unguarded_count"]:
        print(f"::warning::合規.三發現 {domain_scan['unguarded_count']} 處硬寫黑名單網域"
              f"且未import net_guard，見 data/audit_report.json domain_blocklist_scan 欄位")
    if not queue_sync["ok"]:
        print(f"::warning::佇列深度門檻設定不同步，見 data/audit_report.json "
              f"queue_depth_sync 欄位：{queue_sync}")
    if not repro.get("ok", False):
        print(f"::warning::reproducibility_check發現無法import的已登記腳本，"
              f"見 data/audit_report.json reproducibility_check 欄位："
              f"{repro.get('broken') or repro.get('error')}")
    return 0  # 自檢本身不擋住 workflow——就算真的壞了，也要讓後面步驟照跑，
    # 該失敗的地方自然會失敗，這支只負責留下紀錄。


if __name__ == "__main__":
    raise SystemExit(main())
