# -*- coding: utf-8 -*-
"""reproducibility_check.py — 批次確認`TRIALS_LEDGER.md`裡登記過結果的
腳本，現在還能不能被`import`（2026-09-20總司令裁示【Q4前視與#23無法
重現】二.3新增，是`#23`從2026-09-03壞到現在都沒人發現的根本預防）。

**背景**：`piotroski_fscore_sanity.py`（`TRIALS_LEDGER.md`#93）與
`piotroski_fscore_gate_v1.py`（#94）自2026-09-03首次commit起就
`import`一個`pit.py`從未定義過的函式，兩支腳本從那天起就無法執行，
但沒有任何機制發現這件事，直到今天（2026-09-20）研究財報原子庫的
PIT機制時才意外撞見。**登記過的結果，要有機器定期確認它還跑得動**，
這支腳本就是那個機器。

**設計原則（安全考量，務必遵守）**：
1. **只檢查`import`，不執行`main()`**——很多被檢查的腳本頂層就有
   會發真實網路請求的程式碼（例如已停用的MOPS client會在頂層流程裡
   呼叫，一`import`就觸發，這正是它們被停用後仍要用`PermissionError`
   卡住而不是整支刪除的理由——擋在請求真正送出之前）。**每個檢查都
   用獨立子行程＋短逾時**（預設10秒），限制任何頂層副作用的影響範圍，
   不是徹底消除風險（子行程逾時前仍可能已經送出少量真實請求），但
   遠比讓它跑到底安全。
2. **區分「被合規/安全防呆擋下」跟「真的壞掉」**：`PermissionError`
   （`net_guard.py`/既有MOPS client的硬性防呆）代表機制正常運作
   （這支腳本被正確地擋住了，不是壞掉），不列入「需要修的項目」；
   `ImportError`/`ModuleNotFoundError`/`AttributeError`才是需要
   關注的真bug（正是`#23`那種dangling import）。
3. **只檢查`research/`裡確實存在的檔案**——`TRIALS_LEDGER.md`裡提到
   的`.py`檔名，很多是舊版重構後已經改名或整併掉的，本檔案裡找不到
   對應檔案的一律標`FILE_NOT_FOUND`，不當成錯誤（可能是合理的歷史
   演進，不是本次檢查的目標）。

用法：
    python research/reproducibility_check.py
"""
from __future__ import annotations

import json
import random
import re
import subprocess
import sys
from pathlib import Path

try:  # Windows cp950主控台印不出特殊符號時降級，不崩潰（見CLAUDE.md第十二節）
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).parent
TRIALS_LEDGER = ROOT / "TRIALS_LEDGER.md"
OUT_PATH = ROOT / "reproducibility_check_result.json"
TIMEOUT_SECONDS = 10

_PY_NAME_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\.py\b")


def find_ledger_script_names() -> list[str]:
    """從TRIALS_LEDGER.md掃出所有`xxx.py`字面提及，去重、排序。"""
    text = TRIALS_LEDGER.read_text(encoding="utf-8")
    names = sorted(set(_PY_NAME_RE.findall(text)))
    return names


def check_one(module_name: str) -> dict:
    script_path = ROOT / f"{module_name}.py"
    if not script_path.exists():
        return {"module": module_name, "status": "FILE_NOT_FOUND"}

    code = f"import sys; sys.path.insert(0, r'{ROOT}'); import {module_name}"
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=TIMEOUT_SECONDS, cwd=str(ROOT),
        )
    except subprocess.TimeoutExpired:
        return {"module": module_name, "status": "TIMEOUT",
                "note": f"{TIMEOUT_SECONDS}秒內未完成import，可能頂層有重度/網路操作，"
                        f"需要人工檢查是否應該加`if __name__ == '__main__':`保護"}

    if result.returncode == 0:
        return {"module": module_name, "status": "OK"}

    stderr = result.stderr.strip()
    last_line = stderr.splitlines()[-1] if stderr else ""
    if "PermissionError" in stderr:
        return {"module": module_name, "status": "BLOCKED_BY_GUARD",
                "note": "被net_guard/既有合規防呆正確擋下，不是bug", "detail": last_line}
    if any(err in stderr for err in ("ImportError", "ModuleNotFoundError", "AttributeError", "NameError")):
        return {"module": module_name, "status": "IMPORT_ERROR",
                "note": "真的壞了，需要修——這正是#23那種dangling import的同類問題",
                "detail": last_line}
    return {"module": module_name, "status": "OTHER_ERROR", "detail": last_line}


# ── 結果重現抽查（2026-09-20總司令裁示【depth-1閘門設計缺陷要修；
# p=0.053作廢要正式處理】二.3新增）─────────────────────────────────
# 上面的`check_one()`只驗證「能不能import」，這裡更進一步：隨機抽樣
# 已登記數值結果的試驗，**真的重新執行**，比對重跑出來的數字跟登記
# 值是否對得上——這是`#23`（sanity/gate_v1手動重跑）跟三個PASS因子
# （手動重跑）已經做過的事，這裡做成可重複執行、可抽樣任意筆數的
# 通用版本。**誠實的範圍限制（先講清楚，不假裝做到了做不到的事）**：
# 1. 只嘗試「原始程式碼裡`__main__`區塊本身不需要額外命令列參數、
#    且已經通過上面import檢查（狀態OK）」的腳本——不是每一支登記過
#    結果的腳本都符合這個條件，不符合的一律標`COULD_NOT_VERIFY`並
#    寫清楚為什麼，不強行硬跑。
# 2. 比對方式是「重跑輸出裡有沒有一個數字落在登記值的容許誤差內」，
#    不是要求逐位元相同——很多腳本讀的是會持續增長的本機快取（新
#    交易日、新回補的資料），跟三個PASS因子重跑那種「同一組
#    SAMPLE_SEED/SAMPLE_SIZE精確重現」的嚴格度不同，這裡只能檢查
#    「同一個量級的訊號還在不在」，這個限制務必寫進報告，不能讓
#    「重現率」這個數字看起來比實際嚴謹度更高。
NUMERIC_RE = re.compile(r"[-+]?\d+\.\d+")
RERUN_TIMEOUT_SECONDS = 90


def _extract_numbers(text: str) -> list[float]:
    out = []
    for m in NUMERIC_RE.findall(text):
        try:
            out.append(float(m))
        except ValueError:
            continue
    return out


def _numbers_overlap(old: list[float], new: list[float], rel_tol: float = 0.15, abs_tol: float = 1.0) -> bool:
    """任一組數字裡有沒有一對「夠接近」的——相對誤差15%以內或絕對誤差
    1.0以內（涵蓋百分位/IC這種小數值跟百分比alpha這種較大數值兩種
    量級，寧可稍微寬鬆也不要因為誤差帶太窄而把「同一個量級的訊號」
    誤判成沒重現）。

    已知限制（2026-09-20首次抽查發現，記錄不修復，見PROGRESS.md
    對應段落）：這是「任一配對接近就算過」，不要求對應同一個具名
    統計量。對「一支腳本一次算出整批假說結果」這種批次腳本（例如
    `fut_cheap_gate.py`），不同trial重跑會拿到同一份輸出數字清單，
    此時「REPRODUCED」只代表舊登記數字裡有一個巧合地接近新輸出裡
    的某一個，不是這筆trial對應的那個統計量真的重現了——這種案例的
    證據力弱於「一支腳本只對應一筆trial」的情況，解讀重現率時不能
    把兩種案例當同等強度。要收緊需要改成比對「同一位置/同一具名
    統計量」，屬於新架構變更，需先提案，本次不展開做。"""
    for a in old:
        for b in new:
            if abs(a - b) <= abs_tol or (max(abs(a), abs(b)) > 0 and abs(a - b) / max(abs(a), abs(b)) <= rel_tol):
                return True
    return False


def sample_and_rerun(n: int = 10, seed: int | None = None) -> dict:
    """從`trial_registry.py::parse_ledger()`抽`n`筆試驗列，逐一嘗試
    真的重新執行對應腳本並比對數字。回傳含逐筆結果與總結重現率的dict。
    """
    sys.path.insert(0, str(ROOT))
    import trial_registry as tr

    rows = tr.trial_rows(tr.parse_ledger())
    candidates = []
    for r in rows:
        nums = _extract_numbers(r.blob)
        names = sorted(set(_PY_NAME_RE.findall(r.blob)))
        if nums and len(names) == 1:  # 只挑「唯一提到一支腳本、且有數字可比對」的列，避免歧義
            candidates.append((r, names[0], nums))

    rng = random.Random(seed)
    sampled = rng.sample(candidates, k=min(n, len(candidates)))

    results = []
    for r, module_name, old_numbers in sampled:
        script_path = ROOT / f"{module_name}.py"
        entry = {"trial_id": r.tid, "module": module_name, "old_numbers_sample": old_numbers[:5]}
        if not script_path.exists():
            entry["status"] = "COULD_NOT_VERIFY"
            entry["reason"] = "FILE_NOT_FOUND"
            results.append(entry)
            continue
        imp = check_one(module_name)
        if imp["status"] != "OK":
            entry["status"] = "COULD_NOT_VERIFY"
            entry["reason"] = f"import狀態非OK（{imp['status']}），不安全重跑"
            results.append(entry)
            continue
        try:
            proc = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=RERUN_TIMEOUT_SECONDS, cwd=str(ROOT),
            )
        except subprocess.TimeoutExpired:
            entry["status"] = "COULD_NOT_VERIFY"
            entry["reason"] = f"重跑超過{RERUN_TIMEOUT_SECONDS}秒未完成（可能需要即時資料/長時間運算，非本抽查範圍）"
            results.append(entry)
            continue
        if proc.returncode != 0:
            entry["status"] = "COULD_NOT_VERIFY"
            entry["reason"] = f"重跑以非0結束碼結束（{(proc.stderr or '').strip().splitlines()[-1:] or '無stderr'}），"\
                               f"可能需要命令列參數或特定前置狀態，非import層級的bug"
            results.append(entry)
            continue
        new_numbers = _extract_numbers(proc.stdout or "")
        if not new_numbers:
            entry["status"] = "COULD_NOT_VERIFY"
            entry["reason"] = "重跑成功但stdout抓不到可比對的數字"
            results.append(entry)
            continue
        entry["new_numbers_sample"] = new_numbers[:5]
        entry["status"] = "REPRODUCED" if _numbers_overlap(old_numbers, new_numbers) else "DRIFTED"
        results.append(entry)

    verifiable = [r for r in results if r["status"] in ("REPRODUCED", "DRIFTED")]
    reproduced = [r for r in results if r["status"] == "REPRODUCED"]
    rate = (len(reproduced) / len(verifiable)) if verifiable else None
    return {
        "n_sampled": len(sampled),
        "n_candidates_pool": len(candidates),
        "n_could_not_verify": len(results) - len(verifiable),
        "n_verifiable": len(verifiable),
        "n_reproduced": len(reproduced),
        "reproduction_rate_among_verifiable": rate,
        "results": results,
        "scope_caveat": "重現率的分母只有「可以安全重跑並比對數字」的抽樣子集，"
                         "COULD_NOT_VERIFY的筆數另外報告、不算進分母也不算進分子——"
                         "這個數字回答的是「有辦法重跑的那些，跑出來還一樣嗎」，不是"
                         "「TRIALS_LEDGER裡所有結果有多少比例可信」，兩者不能混為一談。",
    }


def main() -> int:
    names = find_ledger_script_names()
    print(f"從TRIALS_LEDGER.md掃出{len(names)}個候選腳本名稱，逐一檢查import...")

    results = []
    for i, name in enumerate(names):
        r = check_one(name)
        results.append(r)
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(names)}")

    by_status: dict[str, list[dict]] = {}
    for r in results:
        by_status.setdefault(r["status"], []).append(r)

    print("\n=== 結果摘要 ===")
    for status in ("OK", "BLOCKED_BY_GUARD", "FILE_NOT_FOUND", "TIMEOUT", "IMPORT_ERROR", "OTHER_ERROR"):
        items = by_status.get(status, [])
        print(f"{status}: {len(items)}")

    broken = by_status.get("IMPORT_ERROR", []) + by_status.get("OTHER_ERROR", [])
    if broken:
        print(f"\n⚠️ 需要修的項目（{len(broken)}個）：")
        for r in broken:
            print(f"  {r['module']}.py — {r['status']}：{r.get('detail', '')}")
    else:
        print("\n沒有發現新的dangling import（除了已經修好的#23）。")

    spot_check = None
    if "--skip-rerun" not in sys.argv:
        print("\n=== 結果重現抽查（隨機抽10筆，實際重跑比對數字）===")
        spot_check = sample_and_rerun(n=10)
        print(f"抽樣池（唯一腳本+有數字可比對）：{spot_check['n_candidates_pool']}筆，"
              f"實際抽樣：{spot_check['n_sampled']}筆")
        print(f"可驗證：{spot_check['n_verifiable']}筆（其中重現{spot_check['n_reproduced']}筆）、"
              f"無法驗證：{spot_check['n_could_not_verify']}筆")
        rate = spot_check["reproduction_rate_among_verifiable"]
        print(f"可驗證子集重現率：{f'{rate:.1%}' if rate is not None else 'N/A（無可驗證樣本）'}")
        print(f"（範圍限制：{spot_check['scope_caveat']}）")
        for r in spot_check["results"]:
            print(f"  #{r['trial_id']} {r['module']}.py — {r['status']}"
                  f"{'：' + r['reason'] if 'reason' in r else ''}")

    OUT_PATH.write_text(json.dumps({
        "checked_at": None,  # 由呼叫端或audit_preflight填,這支本身不依賴系統時間避免時區混淆
        "n_checked": len(names),
        "by_status_count": {k: len(v) for k, v in by_status.items()},
        "broken": broken,
        "all_results": results,
        "result_reproducibility_spot_check": spot_check,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已存：{OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
