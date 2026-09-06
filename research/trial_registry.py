# -*- coding: utf-8 -*-
"""試驗登記強制化：唯一合法的 `TRIALS_LEDGER.md` 寫入口 ＋ 未登記判定的稽核閘門。

（2026-09-07 `PENDING_QUEUE.md` Cybex.債務3。裁示原話：「登記強制化：規則改為
『未呼叫登記函式的候選判定一律無效，不得寫進 LEADS、不得提請審核』」。）

**為什麼需要這支**：`TRIALS_LEDGER.md` 至今是純手工編輯的 markdown 表。手工登記的
後果已經實際發生過三種，全部有證據（見 `REGISTRATION_COVERAGE.md`）：

1. **編號撞號**：#94 與 #149 各自被兩筆完全不同的試驗用掉（不同軌、不同因子），
   所以「編號」根本不能當試驗數的權威來源。
2. **分母寫死**：檔頭「目前累積總數」自 2026-08-23 起被寫死成 37，實際已成長數倍，
   害後續所有多重比較校正用了錯的分母（Cowork.債務2.1 修掉的就是這個）。
3. **沒有機器可讀的副本**：要算 Bonferroni/FDR 分母只能去 regex 一份人寫的散文表，
   每個稽核工具都自己寫一份解析器，彼此結果不一致。

這支的做法：`register_trial()` 是唯一入口，一次寫兩個地方——人看的 markdown 列，
與機器讀的 `research/TRIALS_REGISTRY.jsonl`（append-only，一行一筆 JSON，版控）。
編號由帳本現況推導，不由呼叫端指定，撞號在源頭就不可能發生。

**這支不會去改寫既有的歷史列**（那是 append-only 的歷史證據，改了就毀了）。
歷史列的登記缺口誠實記在 `REGISTRATION_COVERAGE.md`，新的一律走這支。

用法：
    python research/trial_registry.py --check      # 稽核閘門，違規回傳 exit code 1
    python research/trial_registry.py --next-id    # 下一個可用編號
    python research/trial_registry.py --self-test  # 自我測試（只碰暫存檔，不動正式帳本）

程式內：
    from trial_registry import register_trial, assert_registered
    tid = register_trial(track="TW", name="...", design="...", result="...",
                         verdict="FAIL", notes="...", round_no=423)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "research"
LEDGER = RESEARCH / "TRIALS_LEDGER.md"
# 刻意**不**放在 `research/data/`——那整個目錄是 gitignore 的，登記簿放進去等於
# 不存在（`CLAUDE.md` 四之二：當作證據的紀錄必須落地）。它跟 TRIALS_LEDGER.md 同級，
# 是版控的一手證據。
JSONL = RESEARCH / "TRIALS_REGISTRY.jsonl"
TZ = timezone(timedelta(hours=8))

# 新列插在這個錨點正下方（帳本續表是「最新在最上面」的降冪排法）
INSERT_ANCHOR = "## 下一列從這裡開始"
# 2026-08-25 的 FDR 重新評分對照表借用 `#1`..`#17` 引用既有試驗，它不是試驗登記；
# 解析時靠「第二欄是不是日期」把它排除（見 parse_ledger），不靠章節標題。

VALID_TRACKS = ("TW", "US", "FUT", "hypothesis_queue", "跨市場")
# 判定值域跟 `*_LEADS.md` 檔頭那條規則一致，另加 REFUTED（推翻某個解釋假說，
# 不是推翻候選本身）與「未結案」（多關卡假說跑到一半，誠實記錄不硬給判定）。
# 順序有意義：`CHEAP_PASS` 必須排在 `PASS` 前面，否則字串比對會把 CHEAP_PASS 讀成 PASS。
VALID_VERDICTS = ("CHEAP_PASS", "PASS", "FAIL", "EXPERIMENTAL", "ABANDONED", "REFUTED", "未結案")
# 至少要有一個可比較的統計量，否則這一筆對多重比較校正毫無用處
# （債務1 的教訓：73 筆標記通過裡只有 9 筆留下足以重評的統計量）。
STAT_PAT = re.compile(r"百分位|percentile|p\s*[=<>]|IC\s*=|Sharpe|z\s*=|n\s*=\s*\d+")
# 強制化從這天起生效；更早的列是存量債務，只報不擋（見模組說明）。
ENFORCE_FROM = "2026-09-07"


@dataclass
class LedgerRow:
    tid: int
    date: str
    track: str
    verdict: str
    blob: str
    line_no: int
    section: str  # "trial" = 真的試驗登記；"fdr" = 2026-08-25 對照表，不佔編號


def _split_cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_ledger(text: str | None = None) -> list[LedgerRow]:
    """解析帳本所有列。FDR 對照表段落標成 section="fdr"，不參與編號空間。"""
    raw = text if text is not None else LEDGER.read_text(encoding="utf-8")
    rows: list[LedgerRow] = []
    for i, line in enumerate(raw.splitlines(), start=1):
        if not line.startswith("|"):
            continue
        c = _split_cells(line)
        if len(c) < 6 or not re.fullmatch(r"\d+", c[0]):
            continue
        # **試驗列的判準是「第二欄是日期」**，不是靠章節標題判斷區間。
        # 第一版用標題當狀態機，結果把 FDR 對照表之後才續寫的 #39–#62 一起誤判成
        # 對照表（帳本的排版是 FDR 對照表插在主表中間，主表接著往下續寫）。
        # FDR 對照表的第二欄是 `#2` 這種帳本編號引用，不是日期，用這個特徵區分才穩。
        section = "trial" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", c[1]) else "fdr"
        blob = " ".join(c)
        date = c[1] if section == "trial" else ""
        track = next((x for x in c[1:5] if x in VALID_TRACKS), "")
        # 判定欄：**先看倒數第二欄，再往左掃，最後才看備註欄**。
        # 不能單純「從右往左」——最右邊是備註，備註裡常引用別筆的 PASS/FAIL，
        # 從最右邊開始掃會把別人的判定安到這一筆頭上。
        verdict = ""
        for cell in list(reversed(c[2:-1])) + [c[-1]]:
            hit = next((v for v in VALID_VERDICTS if v in cell), "")
            if hit:
                verdict = hit
                break
        rows.append(LedgerRow(int(c[0]), date, track, verdict, blob, i, section))
    return rows


def trial_rows(rows: list[LedgerRow] | None = None) -> list[LedgerRow]:
    return [r for r in (rows if rows is not None else parse_ledger()) if r.section == "trial"]


def next_trial_id(rows: list[LedgerRow] | None = None) -> int:
    """下一個編號 = 現有試驗列最大編號 + 1。由帳本推導，呼叫端不得指定。"""
    ids = [r.tid for r in trial_rows(rows)]
    return (max(ids) + 1) if ids else 1


def _clean(field: str, label: str) -> str:
    """欄位內容淨化：markdown 表格不能有換行或未跳脫的直線符號。"""
    if not isinstance(field, str) or not field.strip():
        raise ValueError(f"登記被拒：`{label}` 是必填，不得留空——留空的登記等於沒登記")
    return " ".join(field.split()).replace("|", "\\|")


def register_trial(
    *,
    track: str,
    name: str,
    design: str,
    result: str,
    verdict: str,
    notes: str,
    round_no: int | None = None,
    round_note: str = "",
    no_stats_reason: str = "",
    date: str = "",
    dry_run: bool = False,
) -> tuple[int, str]:
    """登記一筆試驗。回傳 (編號, 寫進帳本的那一列)。

    參數全部是關鍵字，避免位置參數錯位把「結果」寫到「判定」欄——帳本橫跨多次改版，
    欄序本來就已經不一致過一次了。

    驗證失敗一律 `raise ValueError`，**不會寫任何檔案**：寧可讓那一輪的腳本當場爆掉，
    也不要靜默寫進一筆殘缺的登記（`CLAUDE.md` 七、資料原則：禁止靜默記 None）。
    """
    if track not in VALID_TRACKS:
        raise ValueError(f"登記被拒：軌道 `{track}` 不在值域 {VALID_TRACKS}")
    if verdict not in VALID_VERDICTS:
        raise ValueError(f"登記被拒：判定 `{verdict}` 不在值域 {VALID_VERDICTS}")
    if round_no is not None and not isinstance(round_no, int):
        raise ValueError("登記被拒：`round_no` 必須是整數輪次")
    name_c, design_c, result_c, notes_c = (
        _clean(name, "name"), _clean(design, "design"),
        _clean(result, "result"), _clean(notes, "notes"),
    )
    if not STAT_PAT.search(result_c + " " + notes_c):
        if not no_stats_reason.strip():
            raise ValueError(
                "登記被拒：`result` 找不到任何可比較的統計量（百分位／p 值／IC／n）。"
                "確實沒有統計量就填 `no_stats_reason` 說明為什麼——"
                "債務1 查出 73 筆標記通過裡只有 9 筆留得下足以重評的證據，就是這樣來的"
            )
        notes_c += f"（無統計量原因：{_clean(no_stats_reason, 'no_stats_reason')}）"
    if round_no is None and not round_note.strip():
        raise ValueError("登記被拒：沒有 `round_no` 就必須填 `round_note` 說明這筆不屬於哪一輪馬拉松")
    round_tag = f"round{round_no}" if round_no is not None else _clean(round_note, "round_note")

    stamp = date or datetime.now(TZ).strftime("%Y-%m-%d")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", stamp):
        raise ValueError(f"登記被拒：日期格式錯誤 `{stamp}`")

    tid = next_trial_id(None if dry_run and not LEDGER.exists() else parse_ledger())
    notes_full = f"{notes_c}（登記來源：`trial_registry.register_trial()`，{round_tag}）"
    row = f"| {tid} | {stamp} | {track} | {name_c} | {design_c} | {result_c} | **{verdict}** | {notes_full} |"

    if dry_run:
        return tid, row

    raw = LEDGER.read_text(encoding="utf-8")
    lines = raw.splitlines()
    anchor = next((i for i, l in enumerate(lines) if l.startswith(INSERT_ANCHOR)), -1)
    if anchor < 0:
        raise RuntimeError(f"登記被拒：帳本找不到插入錨點 `{INSERT_ANCHOR}`，不亂寫位置")
    lines.insert(anchor + 1, row)
    LEDGER.write_text("\n".join(lines) + "\n", encoding="utf-8")

    JSONL.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "id": tid, "date": stamp, "track": track, "name": name_c, "design": design_c,
        "result": result_c, "verdict": verdict, "notes": notes_full,
        "round": round_no, "round_note": round_note or None,
        "registered_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "row_sha256": hashlib.sha256(row.encode("utf-8")).hexdigest()[:16],
    }
    with JSONL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return tid, row


def registry_records() -> list[dict]:
    if not JSONL.exists():
        return []
    return [json.loads(l) for l in JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]


def assert_registered(key: str) -> int:
    """寫進 `*_LEADS.md` 之前呼叫：帳本裡找不到這個候選就直接擋下。

    `key` 用因子/策略代碼（例如 `f_low_vol`）或帳本編號（`#123`）。
    """
    rows = trial_rows()
    m = re.fullmatch(r"#?(\d+)", key.strip())
    if m:
        tid = int(m.group(1))
        if any(r.tid == tid for r in rows):
            return tid
        raise ValueError(f"未登記：帳本沒有 #{tid}，這個判定一律無效，不得寫進 LEADS、不得提請審核")
    for r in sorted(rows, key=lambda x: -x.tid):
        if key in r.blob:
            return r.tid
    raise ValueError(f"未登記：帳本找不到 `{key}`，這個判定一律無效，不得寫進 LEADS、不得提請審核")


# ── 稽核閘門 ────────────────────────────────────────────────────────────────
LEADS_FILES = ("LEADS.md", "TW_LEADS.md", "US_LEADS.md", "FUT_LEADS.md")
LEDGER_REF = re.compile(r"TRIALS_LEDGER[^|]{0,40}?#\s*(\d+)|帳本\s*#\s*(\d+)")


def check() -> dict:
    """回傳稽核結果。`violations` 非空代表閘門不通過（強制期內的違規）。"""
    rows = parse_ledger()
    trials = [r for r in rows if r.section == "trial"]
    seen: dict[int, list[int]] = {}
    for r in trials:
        seen.setdefault(r.tid, []).append(r.line_no)
    dup_ids = {k: v for k, v in seen.items() if len(v) > 1}

    ledger_ids = set(seen)
    legacy_unregistered: list[str] = []
    violations: list[str] = []
    checked = 0
    for fname in LEADS_FILES:
        path = RESEARCH / fname
        if not path.exists():
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.startswith("|") or line.startswith("|---"):
                continue
            c = _split_cells(line)
            if len(c) < 4 or not any(v in line for v in VALID_VERDICTS):
                continue
            date = next((x for x in c if re.fullmatch(r"\d{4}-\d{2}-\d{2}", x)), "")
            checked += 1
            m = LEDGER_REF.search(line)
            tid = int(m.group(1) or m.group(2)) if m else None
            if tid is not None and tid in ledger_ids:
                continue
            why = "沒有引用 TRIALS_LEDGER 編號" if tid is None else f"引用的 #{tid} 帳本裡不存在"
            item = f"{fname}:{i} {why}"
            (violations if date >= ENFORCE_FROM else legacy_unregistered).append(item)

    recs = registry_records()
    return {
        "ledger_rows": len(trials),
        "fdr_rows": len(rows) - len(trials),
        "max_id": max(ledger_ids) if ledger_ids else 0,
        "duplicate_ids": {str(k): v for k, v in sorted(dup_ids.items())},
        "leads_rows_checked": checked,
        "violations": violations,
        "legacy_unregistered": legacy_unregistered,
        "structured_records": len(recs),
        "structured_first_id": recs[0]["id"] if recs else None,
        "enforce_from": ENFORCE_FROM,
    }


def _print_check(res: dict) -> int:
    first = res["structured_first_id"]
    print(f"帳本試驗列：{res['ledger_rows']} 列（另有 FDR 對照表 {res['fdr_rows']} 列，不佔編號）")
    print(f"最大編號：#{res['max_id']}；下一個可用編號：#{res['max_id'] + 1}")
    print(f"結構化登記（TRIALS_REGISTRY.jsonl）：{res['structured_records']} 筆"
          + (f"（起於 #{first}）" if first else "（尚無）"))
    if res["duplicate_ids"]:
        print(f"⚠ 撞號 {len(res['duplicate_ids'])} 組（歷史存量，不回頭改寫）：{res['duplicate_ids']}")
    print(f"LEADS 帶判定的列：{res['leads_rows_checked']} 列；"
          f"存量未引用帳本：{len(res['legacy_unregistered'])} 列（{res['enforce_from']} 之前，只報不擋）")
    if res["violations"]:
        print(f"\n✗ FAIL：{len(res['violations'])} 筆 {res['enforce_from']} 起的判定沒有有效帳本登記——"
              "依 `CLAUDE.md` 七之三，這些判定一律無效：")
        for v in res["violations"]:
            print("   -", v)
        return 1
    print("\n✓ PASS：沒有任何強制期內的未登記判定")
    return 0


def _self_test() -> int:
    """自我測試：解析、編號推導、五道拒絕條件，以及暫存目錄裡的完整寫入路徑。

    **不會碰正式帳本**：寫入測試把模組層的 LEDGER/JSONL 暫時指到 tempdir。
    """
    fake = (
        "| # | 日期 | 軌道 | 假說名稱 | 型態 | 關卡結果 | 判定 | 備註 |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| 1 | 2026-08-22 | TW | `f_a` | 因子 | 84.5 百分位 | FAIL | 備註提到別筆的 PASS |\n"
        "## 2026-08-25 FDR重新評分對照表（第二欄是帳本編號引用、不是日期）\n"
        "| 1 | #1 | `f_a` 重新評分 | 100.0 | 0.005 | A | PASS | FDR顯著 |\n"
        f"{INSERT_ANCHOR}\n"
        "| 7 | 2026-09-07 | US | `f_b` | 因子 | IC=+0.03 | CHEAP_PASS | x |\n"
    )
    rows = parse_ledger(fake)
    fails = []
    if len(trial_rows(rows)) != 2:
        fails.append(f"FDR 對照列沒被排除：試驗列數 {len(trial_rows(rows))} != 2")
    if next_trial_id(rows) != 8:
        fails.append(f"編號推導錯：{next_trial_id(rows)} != 8")
    if [r.verdict for r in trial_rows(rows)] != ["FAIL", "CHEAP_PASS"]:
        fails.append(f"判定解析錯（從右往左）：{[r.verdict for r in trial_rows(rows)]}")

    def expect_reject(label: str, **kw) -> None:
        base = dict(track="TW", name="n", design="d", result="99.0 百分位",
                    verdict="FAIL", notes="x", round_no=1, dry_run=True)
        base.update(kw)
        try:
            register_trial(**base)
        except ValueError:
            return
        fails.append(f"應該被拒卻通過了：{label}")

    expect_reject("軌道不在值域", track="TWW")
    expect_reject("判定不在值域", verdict="GOOD")
    expect_reject("必填留空", notes="   ")
    expect_reject("沒有統計量也沒說明原因", result="看起來不錯", notes="沒數字")
    expect_reject("沒有輪次也沒說明", round_no=None, round_note="")

    tid, row = register_trial(track="TW", name="n", design="d", result="99.0 百分位",
                              verdict="FAIL", notes="x", round_no=None,
                              round_note="非馬拉松輪次（自我測試）", dry_run=True)
    if "非馬拉松輪次" not in row or "**FAIL**" not in row:
        fails.append(f"列格式錯：{row}")
    if tid <= 0:
        fails.append(f"編號不合法：{tid}")
    try:
        assert_registered("#999999")
        fails.append("assert_registered 對不存在的編號沒有擋下")
    except ValueError:
        pass

    # 真的寫檔那條路徑也要測，但**絕不碰正式帳本**：改指到暫存目錄跑一次完整登記。
    # 只測 dry_run 等於沒測到插入位置與 JSONL 落地，那正是最容易寫壞的兩段。
    global LEDGER, JSONL  # noqa: PLW0603 — 測試期間暫時改寫，finally 一定還原
    real_ledger, real_jsonl = LEDGER, JSONL
    tmp = Path(tempfile.mkdtemp(prefix="trial_registry_selftest_"))
    try:
        LEDGER, JSONL = tmp / "L.md", tmp / "R.jsonl"
        LEDGER.write_text(fake, encoding="utf-8")
        tid, row = register_trial(track="FUT", name="`fut_x`", design="策略",
                                  result="配對式隨機控制組 93.0 百分位", verdict="CHEAP_PASS",
                                  notes="自我測試", round_no=999)
        after = LEDGER.read_text(encoding="utf-8").splitlines()
        pos = next(i for i, l in enumerate(after) if l.startswith(INSERT_ANCHOR))
        if tid != 8:
            fails.append(f"實寫編號錯：{tid} != 8")
        if after[pos + 1] != row:
            fails.append("新列沒有插在「下一列從這裡開始」的正下方")
        recs = registry_records()
        if len(recs) != 1 or recs[0]["id"] != tid or recs[0]["round"] != 999:
            fails.append(f"JSONL 落地錯：{recs}")
        if next_trial_id() != 9:
            fails.append(f"寫入後編號沒有遞增：{next_trial_id()} != 9")
    except Exception as e:  # noqa: BLE001 — 測試本身失敗也要如實報，不吞掉
        fails.append(f"實寫路徑爆掉：{e!r}")
    finally:
        LEDGER, JSONL = real_ledger, real_jsonl
        shutil.rmtree(tmp, ignore_errors=True)

    for f in fails:
        print("✗", f)
    print("✓ self-test 全過" if not fails else f"✗ self-test {len(fails)} 項失敗")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="試驗登記強制化（Cybex.債務3）")
    ap.add_argument("--check", action="store_true", help="稽核閘門：未登記的判定一律無效")
    ap.add_argument("--next-id", action="store_true", help="印出下一個可用編號")
    ap.add_argument("--self-test", action="store_true", help="自我測試（只碰暫存檔）")
    ap.add_argument("--json", action="store_true", help="--check 改輸出 JSON")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()
    if a.next_id:
        print(next_trial_id())
        return 0
    res = check()
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 1 if res["violations"] else 0
    return _print_check(res)


if __name__ == "__main__":
    sys.exit(main())
