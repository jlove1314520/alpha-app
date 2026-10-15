"""修.FinMind計數（2026-10-15）自測：data/rate_limit_state.json 跨行程鎖。

不打任何外部 API：每個測試把狀態檔／鎖檔路徑換到暫存目錄，最小間隔改成 0.2 秒，
FinMind 方案查詢（_min_interval_sec）換成固定值，所以不會碰到 FinMind／TWSE。

檢查：
A. 兩支行程各用 finmind_client 送 10 次 → calls_by_minute 合計＝20，所有放行時間相鄰間隔 ≥ 最小間隔。
B. 混合三支行程：finmind_client（finmind×10）＋backfill_price_history_gaps（finmind×10）＋
   .github/scripts/fetch_insider_transfer_tw（twse_openapi×10）→ finmind 合計＝20、間隔都 ≥ 最小間隔、
   twse_openapi 的紀錄沒有被 finmind 的寫入蓋掉。
C. 鎖本身壞掉（鎖檔目錄不存在）→ 只印警告、照常放行（十二節 fail open）。
D. 過期鎖（前一個行程死掉留下）→ 自動清掉後取得鎖。
E. record_block 在鎖內寫入封鎖 → 下一次 wait 拋 RuntimeError。
用法：python scripts/selftest_rate_limit_lock.py（全過 exit 0）
"""
from __future__ import annotations

import importlib.util
import json
import multiprocessing as mp
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODS = {
    "fm": ROOT / "research" / "finmind_client.py",
    "bf": ROOT / "research" / "backfill_price_history_gaps.py",
    "gh": ROOT / ".github" / "scripts" / "fetch_insider_transfer_tw.py",
    "fut": ROOT / ".github" / "scripts" / "fetch_futures_institutional.py",
    "p5": ROOT / "research" / "paper_5_vrp_tracker.py",
}
INTERVAL = 0.2
N = 10


def _load(key: str, state_path: Path, lock_path: Path | None = None):
    path = MODS[key]
    for p in (str(path.parent), str(ROOT / "scripts")):
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location(f"_t_{key}", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    if key in ("fut", "p5"):  # 精簡版（固定 3 秒間隔，STATE／STATE_LOCK 變數名）
        m.STATE = state_path
        m.STATE_LOCK = lock_path or state_path.with_name(state_path.name + ".lock")
        return m
    m.RATE_LIMIT_STATE_PATH = state_path
    m.RATE_LIMIT_LOCK_PATH = lock_path or state_path.with_name(state_path.name + ".lock")
    m.RATE_LIMIT_MIN_INTERVAL_SEC = INTERVAL
    if hasattr(m, "_min_interval_sec"):
        m._min_interval_sec = lambda state: INTERVAL
    return m


def _worker(key: str, source: str, state_path: str, q) -> None:
    try:
        m = _load(key, Path(state_path))
        granted = []
        if key in ("fut", "p5"):
            orig_w = m._write_state

            def w(st):
                granted.append(st["sources"][source]["last_request_at"])
                orig_w(st)

            m._write_state = w
            for _ in range(3):
                m._gate() if key == "fut" else _p5_gate(m, source)
            q.put((key, source, granted, None))
            return
        orig_save = m._save_rate_limit_state

        def save(state):  # 只在鎖內被呼叫，記下這次放行的時間
            granted.append(state["sources"][source]["last_request_at"])
            orig_save(state)

        m._save_rate_limit_state = save
        for _ in range(N):
            m._rate_limit_wait_or_raise(source)
        q.put((key, source, granted, None))
    except Exception as e:  # noqa: BLE001
        q.put((key, source, [], repr(e)))


def _p5_gate(m, source):
    """paper_5 的節流寫在 _get() 裡、緊接著送請求；把 requests.request 換成假回應，只測節流。"""
    class _R:
        status_code = 200

        def raise_for_status(self):
            pass

    m.requests.request = lambda *a, **k: _R()
    m._get(source, "GET", "http://invalid.test/")


def _run(jobs, state_path: Path):
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    ps = [ctx.Process(target=_worker, args=(k, s, str(state_path), q)) for k, s in jobs]
    for p in ps:
        p.start()
    res = [q.get(timeout=120) for _ in ps]
    for p in ps:
        p.join(timeout=30)
    return res


def _check_intervals(times, label):
    ts = sorted(times)
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    bad = [g for g in gaps if g < INTERVAL - 1e-6]
    ok = not bad
    print(f"  {'PASS' if ok else 'FAIL'} {label}：{len(ts)} 次放行，最小相鄰間隔 {min(gaps):.3f} 秒（下限 {INTERVAL}）")
    return ok


def _calls(state_path: Path, source: str) -> int:
    st = json.loads(state_path.read_text(encoding="utf-8"))
    return sum(int(v) for v in st["sources"].get(source, {}).get("calls_by_minute", {}).values())


def main() -> int:
    ok = True
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)

        print("A. 兩支行程各 10 次 finmind_client")
        sp = td / "a.json"
        sp.write_text(json.dumps({"sources": {}}), encoding="utf-8")
        res = _run([("fm", "finmind"), ("fm", "finmind")], sp)
        errs = [r[3] for r in res if r[3]]
        c = _calls(sp, "finmind")
        a = not errs and c == 2 * N
        print(f"  {'PASS' if a else 'FAIL'} calls_by_minute 合計 {c}（應為 {2 * N}）{errs or ''}")
        a = _check_intervals([t for r in res for t in r[2]], "finmind 間隔") and a
        ok &= a

        print("B. 混合三支行程（finmind_client＋backfill_price_history_gaps＋fetch_insider_transfer_tw）")
        sp = td / "b.json"
        sp.write_text(json.dumps({"sources": {}}), encoding="utf-8")
        res = _run([("fm", "finmind"), ("bf", "finmind"), ("gh", "twse_openapi")], sp)
        errs = [r[3] for r in res if r[3]]
        c = _calls(sp, "finmind")
        st = json.loads(sp.read_text(encoding="utf-8"))
        gh_last = st["sources"].get("twse_openapi", {}).get("last_request_at")
        gh_granted = max(t for r in res if r[0] == "gh" for t in r[2]) if not errs else None
        b = not errs and c == 2 * N and gh_last == gh_granted
        print(f"  {'PASS' if b else 'FAIL'} finmind 合計 {c}（應為 {2 * N}）、twse_openapi 最後紀錄保留＝{gh_last == gh_granted} {errs or ''}")
        b = _check_intervals([t for r in res if r[1] == "finmind" for t in r[2]], "finmind 跨兩支程式間隔") and b
        ok &= b

        print("C. 鎖壞掉（鎖檔目錄不存在）→ 警告後照常放行")
        sp = td / "c.json"
        m = _load("fm", sp, lock_path=td / "no_such_dir" / "x.lock")
        t0 = time.time()
        m._rate_limit_wait_or_raise("finmind")
        cc = _calls(sp, "finmind") == 1 and time.time() - t0 < 5
        print(f"  {'PASS' if cc else 'FAIL'} 放行 1 次且未卡住")
        ok &= cc

        print("D. 過期鎖自動清掉")
        sp = td / "d.json"
        m = _load("gh", sp)
        m.RATE_LIMIT_LOCK_PATH.write_text("dead", encoding="utf-8")
        old = time.time() - 120
        os.utime(m.RATE_LIMIT_LOCK_PATH, (old, old))
        t0 = time.time()
        m._rate_limit_wait_or_raise("twse_openapi")
        d = time.time() - t0 < 5 and not m.RATE_LIMIT_LOCK_PATH.exists()
        print(f"  {'PASS' if d else 'FAIL'} 取得鎖並釋放（耗時 {time.time() - t0:.2f} 秒）")
        ok &= d

        print("E. record_block 後拒絕送請求")
        sp = td / "e.json"
        e_ok = True
        for key in ("fm", "bf", "gh"):
            m = _load(key, sp)
            try:
                m._rate_limit_record_block("src_" + key, 402, "test") if key != "gh" else m._rate_limit_record_block("src_" + key, 402)
                m._rate_limit_wait_or_raise("src_" + key)
                e_ok = False
                print(f"  FAIL {key}：封鎖後仍放行")
            except RuntimeError:
                pass
        print(f"  {'PASS' if e_ok else 'FAIL'} 三支程式封鎖後都拒絕")
        ok &= e_ok

        print("F. 精簡版（fetch_futures_institutional／paper_5，固定 3 秒）與 finmind_client 同時跑")
        sp = td / "f.json"
        sp.write_text(json.dumps({"sources": {}}), encoding="utf-8")
        res = _run([("fm", "finmind"), ("fut", "taifex_openapi"), ("p5", "taifex_openapi")], sp)
        errs = [r[3] for r in res if r[3]]
        c = _calls(sp, "finmind")
        st = json.loads(sp.read_text(encoding="utf-8"))
        tx = [t for r in res if r[1] == "taifex_openapi" for t in r[2]]
        f_ok = not errs and c == N and st["sources"].get("taifex_openapi", {}).get("last_request_at") == max(tx)
        print(f"  {'PASS' if f_ok else 'FAIL'} finmind 合計 {c}（應為 {N}）、taifex_openapi 最後紀錄保留 {errs or ''}")
        ts = sorted(tx)
        g = min(b - a for a, b in zip(ts, ts[1:]))
        f_ok = f_ok and g >= 3.0 - 1e-6
        print(f"  {'PASS' if g >= 3.0 - 1e-6 else 'FAIL'} taifex_openapi 跨兩支程式 {len(ts)} 次放行，最小間隔 {g:.3f} 秒（下限 3.0）")
        ok &= f_ok

    print("全部通過" if ok else "有失敗")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main())
