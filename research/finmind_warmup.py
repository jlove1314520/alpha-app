"""FinMind 單一預熱抓取者（總司令裁示【先.十】二，2026-10-02）。

這是 paper_supply_v2（紙.二）與 build_supply_watchlist（供給觀察頁）的「唯一」FinMind 抓取者；兩者都改為
LiveSource(read_only=True) / 只讀快取。所有呼叫走 finmind_client._fetch，因此共用同一份
data/rate_limit_state.json 的封鎖狀態與每分鐘呼叫計數（_bump_call_counter）。

用量上限：滾動 1 小時內「所有 FinMind 呼叫（含其他行程）」達 HOURLY_CAP=450 即停（官方免費註冊額度 600/小時，
留 150 給其他排程與重試）。建議由 Task Scheduler 每 15 分鐘叫一次（IgnoreNew），單次最長 MAX_MINUTES 分鐘。

只做「抓資料存快取」：不計算任何報酬、不寫任何紙上交易紀錄、不碰 holdout。快取在 research/data/（git 忽略）。

優先序（高→低）：
  P0 維運（首次換股視窗 10/15 起）：全市場事件表、0050 日線／股利／減資（紙.二日曆）
  P1 即時需求（某季法定期限 D 之後、尚未出訊號）：該季未塵埃落定的財報、價格／事件表（與 paper_supply_v2.run 同判準）；
     以及已出訊號的持股價格（供 _sim_phase 只讀）
  P2 補缺：2024-01 起三種財報 → 2025-01 起價格家族（日價／股利／減資），逐檔、快取檔不存在者
  P3 保鮮：缺目標季的財報檔（視窗前 7 天、視窗內 12 小時以上者，最舊優先）
失敗記憶：同一 (資料集, 代號) 連續失敗 3 次退避 6 小時、5 次退避 24 小時；遇封鎖整輪即停。

用法：
  python research/finmind_warmup.py            # 跑一輪
  python research/finmind_warmup.py --status   # 只印覆蓋率與預估完成時間（不抓）
  python research/finmind_warmup.py --dry      # 列出本輪將抓的前 N 項（不抓）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import finmind_client as fc  # noqa: E402
import paper_supply_v2 as pv2  # noqa: E402

TZ = timezone(timedelta(hours=8))
DATA = HERE / "data"
LOCK_PATH = DATA / "finmind_warmup.lock"
STATE_PATH = DATA / "finmind_warmup_state.json"
STATUS_PATH = DATA / "finmind_warmup_status.json"

HOURLY_CAP = 450
MAX_MINUTES = 14
STMT_FRESH_PRE_WINDOW_H = 7 * 24
STMT_FRESH_IN_WINDOW_H = 12
STALE_LOCK_S = 30 * 60
MIN_TARGET_PERIOD = pd.Period("2026Q2", freq="Q")


def _now():
    return datetime.now(TZ)


def _load_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def _save_json(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(p) + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def _acquire_lock():
    DATA.mkdir(parents=True, exist_ok=True)
    try:
        if LOCK_PATH.exists() and time.time() - LOCK_PATH.stat().st_mtime > STALE_LOCK_S:
            LOCK_PATH.unlink()
        fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f"{os.getpid()} {_now().isoformat(timespec='seconds')}".encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except Exception:  # noqa: BLE001
        return True  # 規則十二：守門員自己出錯時 fail open


def _release_lock():
    try:
        LOCK_PATH.unlink()
    except Exception:  # noqa: BLE001
        pass


# ───────────────────────── 快取掃描 ─────────────────────────
def _paths(code):
    stmt = {k: fc._cache_path(ds, code, pv2.STMT_START, None) for k, ds in pv2.STMT_DS}
    px = {ds: fc._cache_path(ds, code, pv2.PRICE_START, None) for ds in pv2.PRICE_DS}
    return stmt, px


def _max_period(p: Path):
    try:
        df = pd.read_parquet(p, columns=["date"])
        if df.empty:
            return None
        return pd.PeriodIndex(pd.to_datetime(df["date"]), freq="Q").max()
    except Exception:  # noqa: BLE001
        return None


def scan(codes):
    """回傳覆蓋率統計與各類待抓清單（皆為 (ds, code, kind) 序列）。"""
    miss_stmt, miss_px = [], []
    n_stmt_have = n_px_have = n_stmt_nonempty = n_px_nonempty = 0
    full_stmt = full_px = 0
    stale_info = []  # (mtime, code, k, ds)
    now_ts = time.time()
    for c in codes:
        stmt, px = _paths(c)
        s_ok = True
        for (k, ds) in pv2.STMT_DS:
            p = stmt[k]
            if p.exists():
                n_stmt_have += 1
                try:
                    if p.stat().st_size > 2000:
                        n_stmt_nonempty += 1
                except Exception:  # noqa: BLE001
                    pass
                stale_info.append((p.stat().st_mtime, c, k, ds))
            else:
                s_ok = False
                miss_stmt.append((ds, c, "stmt"))
        full_stmt += s_ok
        p_ok = True
        for ds, p in px.items():
            if p.exists():
                n_px_have += 1
                try:
                    if p.stat().st_size > 2000:
                        n_px_nonempty += 1
                except Exception:  # noqa: BLE001
                    pass
            else:
                p_ok = False
                miss_px.append((ds, c, "px"))
        full_px += p_ok
    n = max(1, len(codes))
    return {"n": len(codes),
            "stmt_files_have": n_stmt_have, "stmt_files_total": 3 * len(codes),
            "stmt_codes_complete": full_stmt, "stmt_code_cov": round(full_stmt / n, 4),
            "px_files_have": n_px_have, "px_files_total": 3 * len(codes),
            "px_codes_complete": full_px, "px_code_cov": round(full_px / n, 4),
            "miss_stmt": miss_stmt, "miss_px": miss_px, "stale_info": stale_info,
            "stmt_files_nonempty": n_stmt_nonempty, "px_files_nonempty": n_px_nonempty}


def target_period(now):
    """財報保鮮的目標季：首次換股視窗（法定期限前 30 天）已開的最新一季；視窗未開則為 2026Q2。"""
    tp = MIN_TARGET_PERIOD
    p = pv2.FIRST_PERIOD
    d = pd.Timestamp(now.year, now.month, now.day)
    while d >= pv2.deadline(p) - pd.Timedelta(days=pv2.WINDOW_BEFORE_DAYS):
        tp = p
        p += 1
    return tp


# ───────────────────────── 任務產生 ─────────────────────────
def _fresh_h(ds, code, start, hours):
    p = fc._cache_path(ds, code, start, None)
    return p.exists() and (time.time() - p.stat().st_mtime) < hours * 3600


def gen_tasks(src, uni_codes, now, sc, mem):
    """依優先序產生 (標籤, ds, id, start) 任務；呼叫端負責失敗退避與上限。"""
    now_date = pd.Timestamp(now.year, now.month, now.day)
    first_window = pv2.deadline(pv2.FIRST_PERIOD) - pd.Timedelta(days=pv2.WINDOW_BEFORE_DAYS)
    in_window = now_date >= first_window
    seen = set()

    def emit(tag, ds, code, start):
        key = f"{ds}|{code}"
        if key in seen:
            return None
        seen.add(key)
        return (tag, ds, code, start)

    # P0 維運
    if in_window:
        for ds in pv2.EVENT_DS_ALL:
            if not _fresh_h(ds, "", pv2.PRICE_START, 20):
                t = emit("P0-events", ds, "", pv2.PRICE_START)
                if t:
                    yield t
        for ds, hrs in zip(pv2.PRICE_DS, (3, 20, 20)):
            if not _fresh_h(ds, "0050", pv2.PRICE_START, hrs):
                t = emit("P0-0050", ds, "0050", pv2.PRICE_START)
                if t:
                    yield t
    # P1 即時需求
    if in_window:
        try:
            log_path = pv2.LOG_PATH
            ev, _ = pv2.load_log(log_path)
            keys = {e.get("key") for e in ev}
            cal = src.calendar(now).index
            for p in pv2.periods_until(now_date + pd.Timedelta(days=pv2.WINDOW_BEFORE_DAYS)):
                D = pv2.deadline(p)
                if f"signal|{p}" in keys or f"skip|{p}" in keys or now_date <= D:
                    continue
                for c in uni_codes:
                    ok, miss = pv2._settled(src, c, p, D)
                    for k in miss:
                        ds = dict(pv2.STMT_DS)[k]
                        t = emit("P1-stmt", ds, c, pv2.STMT_START)
                        if t:
                            yield t
                cand = cal[cal <= D]
                if len(cand):
                    need = cand[-1]
                    if not src.events_ready(need):
                        for ds in pv2.EVENT_DS_ALL:
                            t = emit("P1-events", ds, "", pv2.PRICE_START)
                            if t:
                                yield t
                    for c in uni_codes:
                        for ds in src.px_pending(c, need):
                            t = emit("P1-px", ds, c, pv2.PRICE_START)
                            if t:
                                yield t
            last_bar = cal[-1]
            sigs = [e for e in ev if e.get("type") == "signal"]
            hold = sorted({x["code"] for s in sigs for x in s.get("picks", [])})
            for c in hold:
                df, _ = src._cache(pv2.PRICE_DS[0], c)
                if df is None or df.empty or str(df["date"].max()) < str(last_bar.date()):
                    t = emit("P1-hold", pv2.PRICE_DS[0], c, pv2.PRICE_START)
                    if t:
                        yield t
                for ds in pv2.PRICE_DS[1:]:
                    if not _fresh_h(ds, c, pv2.PRICE_START, 20):
                        t = emit("P1-hold", ds, c, pv2.PRICE_START)
                        if t:
                            yield t
        except Exception as e:  # noqa: BLE001  規則十二：偵測失敗只降級，不中斷補缺
            print(f"[警告] P1 即時需求判定失敗，略過：{type(e).__name__}: {e}", flush=True)
    # P2 補缺：財報先、價格後
    for ds, c, _ in sc["miss_stmt"]:
        t = emit("P2-stmt", ds, c, pv2.STMT_START)
        if t:
            yield t
    for ds, c, _ in sc["miss_px"]:
        t = emit("P2-px", ds, c, pv2.PRICE_START)
        if t:
            yield t
    # P3 保鮮：缺目標季的財報檔
    tp = target_period(now)
    age_h = STMT_FRESH_IN_WINDOW_H if in_window else STMT_FRESH_PRE_WINDOW_H
    cutoff = time.time() - age_h * 3600
    for mt, c, k, ds in sorted(sc["stale_info"]):
        if mt >= cutoff:
            break
        p = fc._cache_path(ds, c, pv2.STMT_START, None)
        mp = _max_period(p)
        if mp is None or mp < tp:
            t = emit("P3-stale", ds, c, pv2.STMT_START)
            if t:
                yield t


def _backoff_ok(mem, key, now_ts):
    m = mem.get(key)
    if not m:
        return True
    n = int(m.get("n", 0))
    wait = 24 * 3600 if n >= 5 else (6 * 3600 if n >= 3 else 0)
    return now_ts >= float(m.get("ts", 0)) + wait


# ───────────────────────── 主流程 ─────────────────────────
def write_status(sc, now, extra=None):
    remaining = len(sc["miss_stmt"]) + len(sc["miss_px"])
    eff = HOURLY_CAP * 0.92
    eta_h = remaining / eff if eff else None
    eta = (now + timedelta(hours=eta_h)).isoformat(timespec="minutes") if eta_h is not None else None
    st = {"ts": now.isoformat(timespec="seconds"),
          "universe_n": sc["n"],
          "stmt_code_coverage": sc["stmt_code_cov"], "stmt_codes_complete": sc["stmt_codes_complete"],
          "stmt_files_have": sc["stmt_files_have"], "stmt_files_total": sc["stmt_files_total"],
          "stmt_files_nonempty": sc["stmt_files_nonempty"],
          "px_code_coverage": sc["px_code_cov"], "px_codes_complete": sc["px_codes_complete"],
          "px_files_have": sc["px_files_have"], "px_files_total": sc["px_files_total"],
          "px_files_nonempty": sc["px_files_nonempty"],
          "remaining_backlog_calls": remaining, "hourly_cap": HOURLY_CAP,
          "eta_hours_at_92pct_cap": round(eta_h, 1) if eta_h is not None else None, "eta_local": eta,
          "calls_last_hour": fc.calls_last_hour()}
    if extra:
        st.update(extra)
    _save_json(STATUS_PATH, st)
    return st


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--max-minutes", type=float, default=MAX_MINUTES)
    a = ap.parse_args(argv)
    now = _now()

    src = pv2.LiveSource(read_only=True)
    uni = src.universe()
    codes = list(uni["code"])
    sc = scan(codes)
    if a.status:
        st = write_status(sc, now)
        for k, v in st.items():
            print(f"{k}: {v}")
        return 0

    if not _acquire_lock():
        print("另一輪預熱仍在執行，略過本輪。")
        return 0
    try:
        mem = _load_json(STATE_PATH, {}).get("fails", {})
        start_ts = time.time()
        deadline_ts = start_ts + a.max_minutes * 60
        used = fails_in_row = 0
        by_tag: dict[str, int] = {}
        blocked = False
        stop_reason = "no_more_tasks"
        for tag, ds, code, start in gen_tasks(src, codes, now, sc, mem):
            if time.time() >= deadline_ts:
                stop_reason = "time_budget"
                break
            if fc.calls_last_hour() >= HOURLY_CAP:
                stop_reason = "hourly_cap"
                break
            key = f"{ds}|{code}"
            if not _backoff_ok(mem, key, time.time()):
                continue
            if a.dry:
                print(f"[dry] {tag} {ds} {code or 'ALL'}")
                used += 1
                if used >= 30:
                    break
                continue
            try:
                fc._fetch(ds, code, start, None, force_refresh=True)
                used += 1
                by_tag[tag] = by_tag.get(tag, 0) + 1
                mem.pop(key, None)
                fails_in_row = 0
            except Exception as e:  # noqa: BLE001
                msg = str(e)
                if "封鎖" in msg or "blocked" in msg.lower():
                    blocked = True
                    stop_reason = "blocked"
                    print(f"[停止] FinMind 封鎖中，整輪結束：{msg[:120]}", flush=True)
                    break
                m = mem.get(key, {"n": 0})
                mem[key] = {"n": int(m.get("n", 0)) + 1, "ts": time.time(), "err": msg[:120]}
                fails_in_row += 1
                print(f"[失敗] {tag} {ds} {code}: {msg[:120]}", flush=True)
                if fails_in_row >= 5:
                    stop_reason = "consecutive_fails"
                    break
        if not a.dry:
            _save_json(STATE_PATH, {"fails": mem, "last_run": now.isoformat(timespec="seconds"),
                                    "last_used": used, "last_stop": stop_reason, "by_tag": by_tag})
            sc2 = scan(codes)
            st = write_status(sc2, _now(), {"last_run_calls": used, "last_run_stop": stop_reason, "last_run_by_tag": by_tag,
                                            "blocked": blocked})
            print(f"本輪呼叫 {used} 次（{by_tag}），停止原因 {stop_reason}；滾動1小時總用量 {st['calls_last_hour']}/{HOURLY_CAP}；"
                  f"財報檔 {st['stmt_files_have']}/{st['stmt_files_total']}、價格家族檔 {st['px_files_have']}/{st['px_files_total']}；"
                  f"待補 {st['remaining_backlog_calls']} 次，預估 {st['eta_local']} 完成")
        return 0
    finally:
        _release_lock()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        print(f"[預熱失敗] {type(e).__name__}: {e}", flush=True)
        _release_lock()
        sys.exit(1)
