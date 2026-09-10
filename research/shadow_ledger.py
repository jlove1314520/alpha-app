# -*- coding: utf-8 -*-
"""影子帳本基礎設施（深讀一.1，2026-09-10新增）。

**要解決什麼問題**：`update_strategy_performance.py`目前把每個策略的前向紙上
績效寫進`data/strategy_performance.json`——但那是「整份JSON每天重寫一次」，
不是字面意義的append-only檔案格式：理論上任何人（或任何一次寫檔bug）都可以
改掉去年某一天的`cum_return_pct`，事後完全看不出來，因為沒有任何機制記錄
「這個值曾經是多少、有沒有被改過」。深讀一.3已經把這份資料的MDD/交易數補進
App顯示，但深讀一.3自己的備註已經寫清楚：「影子帳本」這個獨立基礎設施本身
（一個候選機制一本、append-only、可稽核）還沒被蓋出來。這支檔案就是蓋這個。

**設計（刻意做小，不做成一般化的資料庫）**：
- 每個候選機制一個檔案：`research/shadow_ledgers/<mechanism_id>.jsonl`。
- **字面意義的append-only**：只用`open(path, "a")`寫入，程式碼裡完全沒有
  「開檔覆寫」或「讀出全部→改一筆→整份寫回」這種路徑，物理上不給修改過去
  一行的管道。
- **雜湊鏈可稽核**：每一行都帶`prev_hash`（上一行的雜湊）與`hash`
  （這一行內容+prev_hash的SHA256）。要竄改任何一行，之後所有行的雜湊鏈
  都會對不上——`verify_ledger()`重算一次全鏈就能抓到，不必信任檔案本身
  沒被動過手腳。
- **禁止回填**：新的一筆日期必須嚴格大於上一筆，違反就丟例外——跟這個
  repo既有的「forward paper嚴禁事後補建」鐵律（見`update_strategy_
  performance.py`檔頭）同一個精神，用程式碼擋住而不是只寫在文件裡。
- **同日重跑是幂等的**：日期等於最後一筆就直接跳過（回傳None），讓排程
  重跑同一天不會產生兩筆或報錯。

跑法：
    python shadow_ledger.py verify            # 稽核所有機制的雜湊鏈
    python shadow_ledger.py verify <mechanism_id>  # 只稽核一個
這支檔案本身不呼叫任何外部API、不碰網路，純本機檔案操作。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

LEDGER_DIR = Path(__file__).resolve().parent / "shadow_ledgers"
GENESIS_HASH = "GENESIS"


class AppendOnlyViolation(ValueError):
    """試圖回填一個不晚於帳本最後一筆的日期時丟出。"""


def _ledger_path(mechanism_id: str) -> Path:
    return LEDGER_DIR / f"{mechanism_id}.jsonl"


def _read_lines(mechanism_id: str) -> list[dict]:
    path = _ledger_path(mechanism_id)
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _record_hash(prev_hash: str, date: str, mechanism_id: str, payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    raw = f"{prev_hash}|{date}|{mechanism_id}|{canonical}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def append_entry(mechanism_id: str, date: str, payload: dict) -> dict | None:
    """幫`mechanism_id`這本影子帳本append今天這一筆。

    `payload`是這個機制當天的前向績效快照（例如`{daily_pnl_pct, buys, sells,
    n_holdings, cum_return_pct}`），內容不限定格式，只要是可JSON序列化的dict。

    回傳寫入的完整紀錄；若`date`等於帳本最後一筆日期（同日重跑）回傳`None`，
    不重複寫入；若`date`早於帳本最後一筆日期，丟`AppendOnlyViolation`——
    這是刻意設計成硬性拒絕而不是靜默忽略，因為回填過去日期正是這支檔案
    存在的理由所要防止的事。
    """
    existing = _read_lines(mechanism_id)
    if existing:
        last = existing[-1]
        if date == last["date"]:
            return None
        if date < last["date"]:
            raise AppendOnlyViolation(
                f"{mechanism_id}: 試圖寫入 {date}，但帳本最後一筆已經是 {last['date']}"
                "（append-only帳本禁止回填過去日期）")
        prev_hash = last["hash"]
        seq = last["seq"] + 1
    else:
        prev_hash = GENESIS_HASH
        seq = 1

    record = {
        "seq": seq,
        "date": date,
        "mechanism_id": mechanism_id,
        "payload": payload,
        "prev_hash": prev_hash,
        "hash": _record_hash(prev_hash, date, mechanism_id, payload),
    }

    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    path = _ledger_path(mechanism_id)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def verify_ledger(mechanism_id: str) -> tuple[bool, str, int]:
    """重算整條雜湊鏈，回傳(是否通過, 說明, 筆數)。不信任檔案內容本身，
    每一筆的hash都從payload+prev_hash重新算一次比對。"""
    records = _read_lines(mechanism_id)
    if not records:
        return True, "帳本不存在或是空的（尚未有前向資料，不算異常）", 0

    prev_hash = GENESIS_HASH
    prev_date = None
    prev_seq = 0
    for i, rec in enumerate(records):
        expected_hash = _record_hash(prev_hash, rec["date"], rec["mechanism_id"], rec["payload"])
        if rec.get("prev_hash") != prev_hash:
            return False, f"第{i+1}筆（date={rec.get('date')}）prev_hash對不上前一筆的hash，鏈已斷", i + 1
        if rec.get("hash") != expected_hash:
            return False, f"第{i+1}筆（date={rec.get('date')}）內容雜湊對不上，疑似被竄改", i + 1
        if prev_date is not None and rec["date"] <= prev_date:
            return False, f"第{i+1}筆日期{rec['date']}未嚴格晚於前一筆{prev_date}，違反append-only", i + 1
        if rec.get("seq") != prev_seq + 1:
            return False, f"第{i+1}筆seq={rec.get('seq')}不連續（預期{prev_seq+1}）", i + 1
        prev_hash = rec["hash"]
        prev_date = rec["date"]
        prev_seq = rec["seq"]
    return True, f"雜湊鏈完整，共{len(records)}筆，{records[0]['date']}~{records[-1]['date']}", len(records)


def verify_all() -> dict[str, tuple[bool, str, int]]:
    if not LEDGER_DIR.exists():
        return {}
    results = {}
    for path in sorted(LEDGER_DIR.glob("*.jsonl")):
        mechanism_id = path.stem
        results[mechanism_id] = verify_ledger(mechanism_id)
    return results


def _cli() -> int:
    args = sys.argv[1:]
    if not args or args[0] != "verify":
        print(__doc__)
        return 1
    if len(args) >= 2:
        ok, detail, n = verify_ledger(args[1])
        print(f"[{'PASS' if ok else 'FAIL'}] {args[1]}: {detail}")
        return 0 if ok else 1
    results = verify_all()
    if not results:
        print("research/shadow_ledgers/ 底下還沒有任何帳本檔案")
        return 0
    all_ok = True
    for mechanism_id, (ok, detail, n) in results.items():
        print(f"[{'PASS' if ok else 'FAIL'}] {mechanism_id}: {detail}")
        all_ok = all_ok and ok
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(_cli())
