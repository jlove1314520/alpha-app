# -*- coding: utf-8 -*-
"""先.九十五-2：權證每日快照排程本體（本機 Windows 排程 AlphaWarrantSnapshot，週一～五 17:30 台北）。

一次做四件事，各自失敗只記錄、不拖累其他步驟（CLAUDE.md 十二節）：
1. 交易日判斷：data/trading_calendar.json（tw.<年>.closed＋unscheduled_closed）；週末或休市日直接結束，
   不發任何請求。該年行事曆未公布時照平日處理——快照程式本身會核對官方回應日期，休市日不會寫檔。
2. 跑 research/warrant_snapshot.py（每天 7 次請求，節流見該檔；已存在當天資料夾就不重跑）。
3. 每週備份：距上次備份滿 7 天（或從未備份）就把尚未備份過的日資料夾壓成一個 zip，
   存到 research/data 以外的本機資料夾 BACKUP_DIR（總司令指定路徑前的暫定位置），寫完用
   zipfile.testzip() 驗證，驗不過刪掉該 zip、下次再試。
4. 寫 data/warrant_backup_status.json（最後快照日、天數、最後備份時間等，給設定頁顯示）；
   內容有變才用 git_op_lock 取鎖後 path-scoped commit＋push。
   十節註記：本程式會改寫追蹤檔 data/warrant_backup_status.json，dev_queue_runner MACHINE_WRITTEN 以 ^data/ 涵蓋；
   快照與備份本身都不進 repo（research/data/ 已 gitignore，BACKUP_DIR 在 repo 外）。
用法：python research/warrant_snapshot_daily.py [--force-backup] [--no-commit]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent


def _pull_autostash_safe() -> None:
    """先.一〇三-14w：pull --autostash 套回失敗時取回別人未提交的檔（scripts/local_git_commit.py）；匯入失敗退回原本的 pull（十二節）。"""
    try:
        sys.path.insert(0, str(REPO / "scripts"))
        import local_git_commit as _lgc  # noqa: E402
        _lgc.pull_autostash_safe()
    except Exception as e:  # noqa: BLE001
        print(f"[autostash 取回] 警告：{type(e).__name__}: {e}，退回一般 pull", file=sys.stderr)
        subprocess.run(["git", "pull", "-q", "--rebase", "--autostash"], cwd=REPO, capture_output=True, timeout=180)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
TPE = timezone(timedelta(hours=8))
SNAP_ROOT = HERE / "data" / "warrant_snapshots"
BACKUP_DIR = Path(r"C:\alpha\backups\warrant_snapshots")   # 暫定：與 repo 同一顆硬碟，防誤刪不防硬碟故障
MANIFEST = BACKUP_DIR / "backup_manifest.json"
STATUS = REPO / "data" / "warrant_backup_status.json"
CAL = REPO / "data" / "trading_calendar.json"
BACKUP_EVERY = timedelta(days=7)
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def log(msg: str) -> None:
    print(f"[{datetime.now(TPE):%H:%M:%S}] {msg}", flush=True)


def is_trading_day(d: datetime) -> tuple[bool, str]:
    if d.weekday() >= 5:
        return False, "週末"
    try:
        cal = json.loads(CAL.read_text(encoding="utf-8"))["tw"].get(str(d.year)) or {}
        closed = set(cal.get("closed") or []) | set(cal.get("unscheduled_closed") or [])
        if d.strftime("%Y-%m-%d") in closed:
            return False, "休市日（trading_calendar.json）"
        if not cal.get("published"):
            return True, "該年行事曆未公布，照平日處理（快照程式會核對官方日期）"
    except Exception as e:  # noqa: BLE001  行事曆讀不到只降級成平日處理
        return True, f"行事曆讀取失敗（{type(e).__name__}），照平日處理"
    return True, "交易日"


def run_snapshot(day: str) -> tuple[int | None, str]:
    """回傳 (exit code, 失敗原因摘要)；成功或已存在時原因為空字串。"""
    mp = SNAP_ROOT / day / "meta.json"
    if mp.exists():
        try:
            partial = bool(json.loads(mp.read_text(encoding="utf-8")).get("partial"))
        except Exception as e:  # noqa: BLE001  meta 讀不回來就當完整，不重跑（寧可少抓不重複打）
            log(f"{day} meta.json 讀取失敗（{type(e).__name__}），當作已存在")
            partial = False
        if not partial:
            log(f"{day} 快照已存在，不重跑")
            return 0, ""
        log(f"{day} 快照只有部分來源（先.一三二-3），重跑補抓失敗的來源（已抓的不重抓）")
    try:
        r = subprocess.run([sys.executable, str(HERE / "warrant_snapshot.py"), "--date", day], cwd=REPO,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
        last_out = (r.stdout.strip().splitlines() or [""])[-1][:300]
        log(f"warrant_snapshot.py exit={r.returncode} " + last_out)
        last_err = ""
        if r.returncode != 0 and r.stderr.strip():
            last_err = r.stderr.strip().splitlines()[-1][:300]
            log("stderr: " + last_err)
        return r.returncode, ("" if r.returncode == 0 else (last_err or last_out or "（無輸出）"))
    except Exception as e:  # noqa: BLE001
        log(f"快照執行失敗（{type(e).__name__}: {e}）")
        return None, f"{type(e).__name__}: {e}"[:300]


def _days() -> list[str]:
    return sorted(p.name for p in SNAP_ROOT.iterdir() if p.is_dir() and DAY.match(p.name) and (p / "meta.json").exists()) \
        if SNAP_ROOT.exists() else []


def weekly_backup(force: bool) -> dict:
    man = {"backups": [], "backed_up_days": []}
    try:
        if MANIFEST.exists():
            man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        log(f"備份清單讀不回來（{type(e).__name__}），本次不備份以免重複或覆蓋")
        return man
    last = man["backups"][-1]["at"] if man["backups"] else None
    due = force or last is None or datetime.now(TPE) - datetime.fromisoformat(last) >= BACKUP_EVERY
    todo = [d for d in _days() if d not in set(man["backed_up_days"])]
    if not due or not todo:
        log(f"不需備份（上次 {last or '從未'}；待備份 {len(todo)} 天）")
        return man
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    zp = BACKUP_DIR / f"warrant_snapshots_{todo[0]}_{todo[-1]}.zip"
    try:
        with zipfile.ZipFile(zp, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for d in todo:
                for f in sorted((SNAP_ROOT / d).iterdir()):
                    if f.is_file():
                        z.write(f, arcname=f"{d}/{f.name}")
        with zipfile.ZipFile(zp) as z:
            bad = z.testzip()
            n = len(z.namelist())
        if bad is not None:
            raise ValueError(f"zip 驗證失敗：{bad}")
    except Exception as e:  # noqa: BLE001
        log(f"備份失敗（{type(e).__name__}: {e}），刪除不完整的 zip，下次再試")
        zp.unlink(missing_ok=True)
        return man
    man["backups"].append({"at": datetime.now(TPE).isoformat(timespec="seconds"), "file": zp.name,
                           "days": todo, "n_files": n, "bytes": zp.stat().st_size})
    man["backed_up_days"] = sorted(set(man["backed_up_days"]) | set(todo))
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"備份完成：{zp.name}（{len(todo)} 天、{n} 個檔、{zp.stat().st_size / 1e6:.1f}MB，testzip 通過）")
    return man


def write_status(man: dict, failure: dict | None = None) -> bool:
    """failure＝本次快照失敗紀錄（先.一〇九-8：設定頁要看得到漏抓）；沒有就沿用舊檔的 last_failure。"""
    days = _days()
    size = sum(f.stat().st_size for d in days for f in (SNAP_ROOT / d).iterdir() if f.is_file())
    last = man["backups"][-1] if man.get("backups") else None
    st = {"last_snapshot_date": days[-1] if days else None, "snapshot_days": len(days),
          "snapshot_mb": round(size / 1e6, 1),
          "last_backup_at": last["at"] if last else None, "last_backup_file": last["file"] if last else None,
          "backed_up_days": len(man.get("backed_up_days") or []),
          "backup_location": "本機另一個資料夾（C:\\alpha\\backups，與程式同一顆硬碟；總司令指定路徑前的暫定位置）",
          "schedule": "本機排程 AlphaWarrantSnapshot：交易日 17:30 快照、每 7 天備份一次",
          "note": "先.九十五-2。快照與備份都只存本機，不進 repo。非投資建議。"}
    old = None
    try:
        old = json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else None
    except Exception as e:  # noqa: BLE001
        log(f"舊狀態檔讀不回來（{type(e).__name__}），照新內容重寫")
    lf = failure or (old or {}).get("last_failure")
    if lf:
        st["last_failure"] = lf
    if old and {k: v for k, v in old.items() if k != "generated_at"} == st:
        log("狀態沒變，不重寫")
        return False
    st = {"generated_at": datetime.now(TPE).isoformat(timespec="seconds"), **st}
    STATUS.write_text(json.dumps(st, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log(f"寫入 {STATUS.name}：最後快照 {st['last_snapshot_date']}、最後備份 {st['last_backup_at']}")
    return True


def commit_status() -> None:
    g = lambda *a: subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:  # 先.一〇三-15ag：git 改走 local_git_commit.run_git（逾時殺整棵行程樹、禁止互動式認證），匯入失敗退回原寫法（十二節）（原本沒有逾時，改為 180 秒）
        sys.path.insert(0, str(REPO / "scripts"))
        from local_git_commit import run_git
        g = lambda *a: run_git(a, cwd=REPO, timeout=180)  # noqa: E731
    except ImportError:
        pass
    tok = None
    try:
        for _ in range(40):
            r = subprocess.run([sys.executable, str(HERE / "git_op_lock.py"), "acquire"], cwd=REPO, capture_output=True, text=True)
            m = re.search(r"token=(\w+)", r.stdout or "")
            if r.returncode == 0 and m:
                tok = m.group(1)
                break
            subprocess.run([sys.executable, "-c", "import time;time.sleep(3)"])
        if not tok:
            log("拿不到 git_op_lock，本次不提交（狀態檔留在本機，下次一起送）")
            return
        rel = "data/warrant_backup_status.json"
        c = g("commit", "-o", "-m", "權證快照備份狀態自動更新（先.九十五-2，AlphaWarrantSnapshot）\n\n"
              "十節註記：本排程只改寫 data/warrant_backup_status.json（path-scoped commit），"
              "dev_queue_runner MACHINE_WRITTEN 以 ^data/ 涵蓋。", "--", rel)
        if c.returncode != 0:
            log("commit 失敗：" + (c.stderr or c.stdout).strip()[-200:])
            return
        for i in range(3):
            p = g("push", "-q")
            if p.returncode == 0:
                log("push 成功")
                return
            _pull_autostash_safe()
        log("push 失敗 3 次，commit 留在本機，下次一起送")
    except Exception as e:  # noqa: BLE001
        log(f"提交失敗（{type(e).__name__}: {e}）")
    finally:
        if tok:
            subprocess.run([sys.executable, str(HERE / "git_op_lock.py"), "release", "--token", tok], cwd=REPO, capture_output=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-backup", action="store_true")
    ap.add_argument("--no-commit", action="store_true")
    a = ap.parse_args()
    now = datetime.now(TPE)
    ok, why = is_trading_day(now)
    log(f"{now:%Y-%m-%d}：{why}")
    failure = None
    if ok:
        day = now.strftime("%Y-%m-%d")
        rc, why_fail = run_snapshot(day)
        if rc != 0:  # 2＝限流封鎖、3＝官方回應驗證不過、4＝部分來源失敗（成功的已寫）、1／None＝其他錯誤
            failure = {"date": day, "exit": rc, "reason": why_fail,
                       "at": datetime.now(TPE).isoformat(timespec="seconds")}
    man = weekly_backup(a.force_backup)
    if write_status(man, failure) and not a.no_commit:
        commit_status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
